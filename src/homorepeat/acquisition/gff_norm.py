"""GFF-backed linkage helpers for CDS normalization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(slots=True)
class LinkageRecord:
    """Resolved transcript/CDS linkage metadata."""

    gene_symbol: str
    transcript_id: str
    protein_external_id: str
    translation_table: str
    source_record_id: str
    partial_status: str
    match_source: str


TRANSCRIPT_LIKE_FEATURE_TYPES = {
    "mrna",
    "transcript",
    "rna",
    "ncrna",
    "v_gene_segment",
    "d_gene_segment",
    "j_gene_segment",
    "c_gene_segment",
}


def build_gff_index(
    path: Path | str,
    *,
    allowed_sequence_accessions: set[str] | None = None,
) -> dict[str, dict[str, LinkageRecord]]:
    """Index common lookup keys from one GFF file."""

    gff_path = Path(path)
    genes: dict[str, dict[str, str]] = {}
    transcripts: dict[str, dict[str, str]] = {}
    cds_records_by_transcript: dict[str, dict[str, str]] = {}
    cds_transcript_aliases: dict[str, set[str]] = {}
    cds_source_aliases: dict[str, set[str]] = {}
    allowed_seqids = set(allowed_sequence_accessions) if allowed_sequence_accessions else None

    with gff_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 9:
                continue
            seqid = parts[0]
            if allowed_seqids is not None and seqid not in allowed_seqids:
                continue
            feature_type = parts[2]
            attributes = parse_gff_attributes(parts[8])
            if feature_type == "gene":
                gene_id = attributes.get("ID", "")
                if gene_id:
                    genes[gene_id] = {
                        "gene_symbol": first_nonempty(
                            attributes.get("gene"),
                            attributes.get("Name"),
                            attributes.get("locus_tag"),
                            extract_dbxref_value(attributes.get("Dbxref", ""), "GeneID"),
                        ),
                    }
                continue

            if feature_type.lower() in TRANSCRIPT_LIKE_FEATURE_TYPES:
                transcript_feature_id = attributes.get("ID", "")
                if transcript_feature_id:
                    parent_gene_id = first_parent(attributes.get("Parent", ""))
                    transcript_info = {
                        "feature_id": transcript_feature_id,
                        "parent_gene_id": parent_gene_id,
                        "gene_symbol": first_nonempty(
                            attributes.get("gene"),
                            genes.get(parent_gene_id, {}).get("gene_symbol", ""),
                        ),
                        "transcript_label": first_nonempty(
                            attributes.get("transcript_id"),
                            extract_dbxref_value(attributes.get("Dbxref", ""), "GenBank"),
                            attributes.get("standard_name"),
                            attributes.get("Name", ""),
                            transcript_feature_id,
                        ),
                    }
                    aliases = {
                        transcript_feature_id,
                        transcript_info["transcript_label"],
                        extract_dbxref_value(attributes.get("Dbxref", ""), "GenBank"),
                        attributes.get("Name", ""),
                    }
                    for alias in filter(None, aliases):
                        transcripts[alias] = transcript_info
                continue

            if feature_type != "CDS":
                continue

            dbxref = attributes.get("Dbxref", "")
            parent_transcript_id = first_parent(attributes.get("Parent", ""))
            transcript_id = first_nonempty(
                attributes.get("transcript_id"),
                extract_dbxref_value(dbxref, "GenBank"),
                parent_transcript_id,
            )
            if not transcript_id:
                continue
            cds_key = first_nonempty(parent_transcript_id, transcript_id)
            existing = cds_records_by_transcript.setdefault(
                cds_key,
                {
                    "source_record_id": attributes.get("ID", ""),
                    "protein_external_id": attributes.get("protein_id", ""),
                    "translation_table": attributes.get("transl_table", ""),
                    "partial_status": "",
                    "preferred_transcript_id": transcript_id,
                },
            )
            if not existing["source_record_id"] and attributes.get("ID"):
                existing["source_record_id"] = attributes["ID"]
            if not existing["protein_external_id"] and attributes.get("protein_id"):
                existing["protein_external_id"] = attributes["protein_id"]
            if not existing["translation_table"] and attributes.get("transl_table"):
                existing["translation_table"] = attributes["transl_table"]
            if not existing["preferred_transcript_id"] and transcript_id:
                existing["preferred_transcript_id"] = transcript_id
            if _is_partial(attributes):
                existing["partial_status"] = "partial"
            cds_transcript_aliases.setdefault(cds_key, set()).update(
                filter(
                    None,
                    {
                        parent_transcript_id,
                        transcript_id,
                        attributes.get("transcript_id", ""),
                        extract_dbxref_value(dbxref, "GenBank"),
                    },
                )
            )
            cds_source_aliases.setdefault(cds_key, set()).update(
                filter(
                    None,
                    {
                        attributes.get("ID", ""),
                        first_nonempty(
                            f"cds-{attributes.get('protein_id', '')}" if attributes.get("protein_id") else "",
                            "",
                        ),
                    },
                )
            )

    transcript_map: dict[str, LinkageRecord] = {}
    protein_map: dict[str, LinkageRecord] = {}
    cds_map: dict[str, LinkageRecord] = {}
    for transcript_key, cds_info in cds_records_by_transcript.items():
        transcript_info: dict[str, str] = {}
        for alias in [transcript_key, *sorted(cds_transcript_aliases.get(transcript_key, set()))]:
            candidate = transcripts.get(alias, {})
            if candidate:
                transcript_info = candidate
                break
        parent_gene_id = transcript_info.get("parent_gene_id", "")
        gene_symbol = first_nonempty(
            transcript_info.get("gene_symbol", ""),
            genes.get(parent_gene_id, {}).get("gene_symbol", ""),
        )
        linkage = LinkageRecord(
            gene_symbol=gene_symbol,
            transcript_id=first_nonempty(
                transcript_info.get("transcript_label", ""),
                cds_info.get("preferred_transcript_id", ""),
                transcript_key,
            ),
            protein_external_id=cds_info.get("protein_external_id", ""),
            translation_table=cds_info.get("translation_table", ""),
            source_record_id=cds_info.get("source_record_id", ""),
            partial_status=cds_info.get("partial_status", ""),
            match_source="gff",
        )
        transcript_aliases = {
            transcript_key,
            linkage.transcript_id,
            transcript_info.get("feature_id", ""),
            transcript_info.get("transcript_label", ""),
        }
        transcript_aliases.update(cds_transcript_aliases.get(transcript_key, set()))
        for alias in filter(None, transcript_aliases):
            transcript_map[alias] = linkage

        protein_aliases = {
            linkage.protein_external_id,
            f"cds-{linkage.protein_external_id}" if linkage.protein_external_id else "",
        }
        for alias in filter(None, protein_aliases):
            protein_map[alias] = linkage

        cds_aliases = {linkage.source_record_id}
        cds_aliases.update(cds_source_aliases.get(transcript_key, set()))
        for alias in filter(None, cds_aliases):
            cds_map[alias] = linkage

    return {
        "transcript": transcript_map,
        "protein": protein_map,
        "cds": cds_map,
    }


def resolve_linkage(
    header_metadata: dict[str, str],
    gff_index: dict[str, dict[str, LinkageRecord]],
) -> LinkageRecord | None:
    """Resolve FASTA metadata through the indexed GFF relationships."""

    record_id = header_metadata.get("record_id", "")
    transcript_id = header_metadata.get("transcript_id", "")
    protein_id = header_metadata.get("protein_id", "")
    gene_symbol = header_metadata.get("gene", "")
    exception_text = header_metadata.get("exception", "").lower()
    dbxref_genbank = extract_dbxref_value(header_metadata.get("db_xref", ""), "GenBank")
    derived_cds_id = derive_cds_id_from_record_id(record_id)

    for key in [transcript_id, dbxref_genbank, record_id]:
        if key and key in gff_index["transcript"]:
            return gff_index["transcript"][key]
    for key in [protein_id, f"cds-{protein_id}" if protein_id else ""]:
        if key and key in gff_index["protein"]:
            return gff_index["protein"][key]
    for key in [record_id, derived_cds_id]:
        if key and key in gff_index["cds"]:
            return gff_index["cds"][key]
    if (
        gene_symbol
        and not transcript_id
        and not protein_id
        and "rearrangement required for product" in exception_text
    ):
        gene_segment_cds_id = f"cds-{gene_symbol}"
        linkage = gff_index["cds"].get(gene_segment_cds_id)
        if linkage is not None:
            return replace(
                linkage,
                gene_symbol=first_nonempty(linkage.gene_symbol, gene_symbol),
                match_source="gff_gene_segment_alias",
            )
    return None


def derive_cds_id_from_record_id(record_id: str) -> str:
    """Derive a likely GFF CDS id from an NCBI CDS FASTA record id."""

    if "_cds_" not in record_id:
        return ""
    suffix = record_id.split("_cds_", 1)[1]
    protein_token, separator, _ = suffix.rpartition("_")
    if separator and protein_token:
        return f"cds-{protein_token}"
    return ""


def parse_gff_attributes(value: str) -> dict[str, str]:
    """Parse a semicolon-delimited GFF3 attributes field."""

    attributes: dict[str, str] = {}
    for chunk in value.split(";"):
        item = chunk.strip()
        if not item:
            continue
        key, sep, raw_value = item.partition("=")
        if not sep:
            continue
        attributes[key] = raw_value
    return attributes


def extract_dbxref_value(dbxref_value: str, prefix: str) -> str:
    """Return the value for one ``Dbxref`` prefix, if present."""

    for item in dbxref_value.split(","):
        item = item.strip()
        if item.startswith(f"{prefix}:"):
            return item.split(":", 1)[1]
    return ""


def first_parent(value: str) -> str:
    return value.split(",")[0].strip() if value else ""


def first_nonempty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def _is_partial(attributes: dict[str, str]) -> bool:
    return any(
        [
            attributes.get("partial", "").lower() == "true",
            bool(attributes.get("start_range")),
            bool(attributes.get("end_range")),
        ]
    )
