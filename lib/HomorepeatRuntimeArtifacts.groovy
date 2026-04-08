import groovy.json.JsonOutput
import groovy.json.JsonSlurper

import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.Paths
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class HomorepeatRuntimeArtifacts {
    private static final Map<String, Map<String, String>> PUBLISHED_ARTIFACTS = [
        acquisition: [
            genomes_tsv                : 'acquisition/genomes.tsv',
            taxonomy_tsv               : 'acquisition/taxonomy.tsv',
            sequences_tsv              : 'acquisition/sequences.tsv',
            proteins_tsv               : 'acquisition/proteins.tsv',
            cds_fasta                  : 'acquisition/cds.fna',
            proteins_fasta             : 'acquisition/proteins.faa',
            download_manifest_tsv      : 'acquisition/download_manifest.tsv',
            normalization_warnings_tsv : 'acquisition/normalization_warnings.tsv',
            acquisition_validation_json: 'acquisition/acquisition_validation.json',
        ],
        calls      : [
            repeat_calls_tsv: 'calls/repeat_calls.tsv',
            run_params_tsv  : 'calls/run_params.tsv',
            finalized_root : 'calls/finalized',
        ],
        database   : [
            sqlite                : 'database/homorepeat.sqlite',
            sqlite_validation_json: 'database/sqlite_validation.json',
        ],
        reports    : [
            summary_by_taxon_tsv: 'reports/summary_by_taxon.tsv',
            regression_input_tsv: 'reports/regression_input.tsv',
            echarts_options_json: 'reports/echarts_options.json',
            echarts_report_html : 'reports/echarts_report.html',
            echarts_js          : 'reports/echarts.min.js',
        ],
        status     : [
            accession_status_tsv     : 'status/accession_status.tsv',
            accession_call_counts_tsv: 'status/accession_call_counts.tsv',
            status_summary_json      : 'status/status_summary.json',
        ],
        metadata   : [
            launch_metadata_json : 'metadata/launch_metadata.json',
            nextflow_report_html : 'metadata/nextflow/report.html',
            nextflow_timeline_html: 'metadata/nextflow/timeline.html',
            nextflow_dag_html    : 'metadata/nextflow/dag.html',
            trace_txt            : 'metadata/nextflow/trace.txt',
        ],
    ]

    static void finalizeRun(Map ctx) {
        Path repoRoot = asPath(ctx.repoRoot)
        Path launchDir = asPath(ctx.launchDir)
        Path runRoot = resolveAgainstLaunchDir(ctx.runRoot, launchDir)
        Path publishRoot = resolveAgainstLaunchDir(ctx.publishRoot, launchDir)
        Path accessionsFile = resolveAgainstLaunchDir(ctx.accessionsFile, launchDir)
        Path taxonomyDb = resolveAgainstLaunchDir(ctx.taxonomyDb, launchDir)
        Path workDir = ctx.workDir ? asPath(ctx.workDir) : null
        String paramsFileValue = extractOption(ctx.commandLine?.toString(), ['-params-file', '--params-file'])
        Path paramsFile = resolveAgainstLaunchDir(paramsFileValue, launchDir)
        String logFileValue = extractOption(ctx.commandLine?.toString(), ['-log', '--log'])
        Path nextflowLog = resolveAgainstLaunchDir(logFileValue, launchDir)

        Path internalDir = runRoot.resolve('internal').resolve('nextflow')
        Path metadataDir = publishRoot.resolve('metadata')
        Path publishedNextflowDir = metadataDir.resolve('nextflow')
        Files.createDirectories(internalDir)
        Files.createDirectories(publishedNextflowDir)

        linkPublishedPath(internalDir.resolve('report.html'), publishedNextflowDir.resolve('report.html'))
        linkPublishedPath(internalDir.resolve('timeline.html'), publishedNextflowDir.resolve('timeline.html'))
        linkPublishedPath(internalDir.resolve('dag.html'), publishedNextflowDir.resolve('dag.html'))
        linkPublishedPath(internalDir.resolve('trace.txt'), publishedNextflowDir.resolve('trace.txt'))
        cleanupWorkflowOutputPlaceholders(publishRoot)

        Path launchMetadataPath = metadataDir.resolve('launch_metadata.json')
        writeJson(
            launchMetadataPath,
            buildLaunchMetadata(
                runId: ctx.runId?.toString() ?: '',
                profile: ctx.profile?.toString() ?: '',
                status: ctx.status?.toString() ?: '',
                startedAtUtc: formatUtc(ctx.startedAt),
                finishedAtUtc: formatUtc(ctx.finishedAt),
                launchDir: launchDir,
                repoRoot: repoRoot,
                runRoot: runRoot,
                publishRoot: publishRoot,
                workDir: workDir,
                accessionsFile: accessionsFile,
                taxonomyDb: taxonomyDb,
                paramsFile: paramsFile,
                nextflowLog: nextflowLog,
                runName: ctx.runName?.toString() ?: '',
                success: !!ctx.success,
                resumeUsed: hasFlag(ctx.commandLine?.toString(), '-resume'),
            ),
        )

        writeJson(
            metadataDir.resolve('run_manifest.json'),
            buildRunManifest(
                repoRoot: repoRoot,
                runId: ctx.runId?.toString() ?: '',
                runRoot: runRoot,
                publishRoot: publishRoot,
                profile: ctx.profile?.toString() ?: '',
                accessionsFile: accessionsFile,
                taxonomyDb: taxonomyDb,
                paramsFile: paramsFile,
                launchMetadata: launchMetadataPath,
                startedAtUtc: formatUtc(ctx.startedAt),
                finishedAtUtc: formatUtc(ctx.finishedAt),
                status: ctx.status?.toString() ?: '',
            ),
        )

        if (ctx.success) {
            updateLatestSymlink(repoRoot, ctx.runId?.toString() ?: '')
        }
    }

    private static void cleanupWorkflowOutputPlaceholders(Path publishRoot) {
        Path placeholderDir = publishRoot.resolve('.nf_placeholders')
        if (!Files.exists(placeholderDir, LinkOption.NOFOLLOW_LINKS)) {
            return
        }
        placeholderDir.toFile().deleteDir()
    }

    private static Map<String, Object> buildLaunchMetadata(Map ctx) {
        [
            run_id         : ctx.runId,
            status         : ctx.status,
            started_at_utc : ctx.startedAtUtc,
            finished_at_utc: ctx.finishedAtUtc,
            profile        : ctx.profile,
            launch_dir     : ctx.launchDir?.toString() ?: '',
            project_dir    : ctx.repoRoot?.toString() ?: '',
            inputs         : [
                accessions_file: ctx.accessionsFile?.toString() ?: '',
                taxonomy_db    : ctx.taxonomyDb?.toString() ?: '',
                params_file    : ctx.paramsFile?.toString() ?: '',
            ],
            paths          : [
                run_root    : ctx.runRoot?.toString() ?: '',
                publish_root: ctx.publishRoot?.toString() ?: '',
                work_dir    : ctx.workDir?.toString() ?: '',
                nextflow_log: ctx.nextflowLog?.toString() ?: '',
                trace_txt   : ctx.runRoot ? ctx.runRoot.resolve('internal/nextflow/trace.txt').toString() : '',
            ],
            nextflow       : [
                run_name   : ctx.runName,
                success    : ctx.success,
                resume_used: ctx.resumeUsed,
            ],
        ]
    }

    private static Map<String, Object> buildRunManifest(Map ctx) {
        Path repoRoot = ctx.repoRoot as Path
        Path runRoot = ctx.runRoot as Path
        Path publishRoot = ctx.publishRoot as Path

        [
            run_id         : ctx.runId,
            status         : ctx.status?.toString() ?: '',
            started_at_utc : ctx.startedAtUtc,
            finished_at_utc: ctx.finishedAtUtc,
            profile        : ctx.profile,
            git_revision   : gitRevision(repoRoot),
            inputs         : [
                accessions_file: relativeOrAbsolute(ctx.accessionsFile as Path, repoRoot),
                taxonomy_db    : relativeOrAbsolute(ctx.taxonomyDb as Path, repoRoot),
                params_file    : ctx.paramsFile ? relativeOrAbsolute(ctx.paramsFile as Path, repoRoot) : '',
            ],
            paths          : [
                run_root    : relativeOrAbsolute(runRoot, repoRoot),
                publish_root: relativeOrAbsolute(publishRoot, repoRoot),
            ],
            params         : manifestParams(
                publishRoot: publishRoot,
                paramsFile: ctx.paramsFile as Path,
                runRoot: runRoot,
            ),
            enabled_methods: enabledMethods(publishRoot),
            repeat_residues: repeatResidues(publishRoot),
            artifacts      : collectArtifacts(runRoot, publishRoot),
        ]
    }

    private static Map<String, Object> manifestParams(Map ctx) {
        Map<String, Object> payload = [
            run_root          : (ctx.runRoot as Path).toString(),
            publish_root      : (ctx.publishRoot as Path).toString(),
            params_file_values: [:],
            detection         : readMethodParams(ctx.publishRoot as Path),
        ]

        Path paramsFile = ctx.paramsFile as Path
        if (paramsFile && Files.isRegularFile(paramsFile)) {
            try {
                def parsed = new JsonSlurper().parse(paramsFile.toFile())
                payload.params_file_values = parsed instanceof Map ? parsed : [:]
            } catch (Exception ignored) {
                payload.params_file_values = [:]
            }
        }

        payload
    }

    private static List<String> enabledMethods(Path publishRoot) {
        new ArrayList<>(readMethodParams(publishRoot).keySet()).sort()
    }

    private static List<String> repeatResidues(Path publishRoot) {
        Set<String> residues = new TreeSet<>()
        readMethodParams(publishRoot).values().each { Map<String, Map<String, String>> methodPayload ->
            methodPayload.keySet().each { String residue ->
                if (residue) {
                    residues.add(residue)
                }
            }
        }
        new ArrayList<>(residues)
    }

    private static Map<String, Map<String, Map<String, String>>> readMethodParams(Path publishRoot) {
        Path runParamsPath = publishRoot.resolve('calls').resolve('run_params.tsv')
        if (!Files.isRegularFile(runParamsPath)) {
            return [:]
        }

        Map<String, Map<String, Map<String, String>>> payload = [:].withDefault { [:].withDefault { [:] } }
        readTsvRows(runParamsPath).each { Map<String, String> row ->
            String method = row.get('method', '')
            String repeatResidue = row.get('repeat_residue', '')
            String paramName = row.get('param_name', '')
            if (method && repeatResidue && paramName) {
                payload[method][repeatResidue][paramName] = row.get('param_value', '')
            }
        }
        payload.collectEntries { String method, Map<String, Map<String, String>> residueMap ->
            [(method): residueMap.collectEntries { String residue, Map<String, String> values ->
                [(residue): new TreeMap<>(values)]
            }]
        }
    }

    private static Map<String, Map<String, String>> collectArtifacts(Path runRoot, Path publishRoot) {
        Map<String, Map<String, String>> payload = [:]
        PUBLISHED_ARTIFACTS.each { String section, Map<String, String> files ->
            Map<String, String> sectionPayload = [:]
            files.each { String key, String relativePath ->
                Path candidate = publishRoot.resolve(relativePath).normalize()
                if (Files.exists(candidate) || Files.exists(candidate, LinkOption.NOFOLLOW_LINKS)) {
                    sectionPayload[key] = relativeOrAbsolute(candidate, runRoot)
                }
            }
            payload[section] = sectionPayload
        }
        payload
    }

    private static List<Map<String, String>> readTsvRows(Path path) {
        List<String> lines = Files.readAllLines(path)
        if (!lines) {
            return []
        }

        List<String> header = lines.first().split('\t', -1) as List<String>
        List<Map<String, String>> rows = []
        lines.drop(1).findAll { it != null && it != '' }.each { String line ->
            List<String> values = line.split('\t', -1) as List<String>
            Map<String, String> row = [:]
            header.eachWithIndex { String key, int index ->
                row[key] = index < values.size() ? values[index] : ''
            }
            rows << row
        }
        rows
    }

    private static String gitRevision(Path repoRoot) {
        try {
            def process = new ProcessBuilder('git', 'rev-parse', 'HEAD')
                .directory(repoRoot.toFile())
                .redirectErrorStream(true)
                .start()
            String output = process.inputStream.getText('UTF-8').trim()
            process.waitFor()
            return process.exitValue() == 0 ? output : ''
        } catch (Exception ignored) {
            return ''
        }
    }

    private static void updateLatestSymlink(Path repoRoot, String runId) {
        if (!runId) {
            return
        }

        Path latestLink = repoRoot.resolve('runs').resolve('latest')
        Files.createDirectories(latestLink.parent)
        try {
            Files.deleteIfExists(latestLink)
            Files.createSymbolicLink(latestLink, Paths.get(runId))
        } catch (UnsupportedOperationException | SecurityException ignored) {
            // best-effort only
        } catch (IOException ignored) {
            // best-effort only
        }
    }

    private static void writeJson(Path path, Map<String, Object> payload) {
        Files.createDirectories(path.parent)
        Files.writeString(
            path,
            JsonOutput.prettyPrint(JsonOutput.toJson(payload)) + '\n',
        )
    }

    private static void linkPublishedPath(Path source, Path destination) {
        Files.createDirectories(destination.parent)
        Files.deleteIfExists(destination)
        Path relativeSource = destination.parent.relativize(source)
        Files.createSymbolicLink(destination, relativeSource)
    }

    private static Path resolveAgainstLaunchDir(Object rawPath, Path launchDir) {
        if (rawPath == null) {
            return null
        }

        String value = rawPath.toString().trim()
        if (!value) {
            return null
        }

        Path path = Paths.get(value)
        if (!path.isAbsolute()) {
            path = launchDir.resolve(path)
        }
        path.normalize().toAbsolutePath()
    }

    private static Path asPath(Object value) {
        value instanceof Path ? (value as Path).toAbsolutePath().normalize() : Paths.get(value.toString()).toAbsolutePath().normalize()
    }

    private static String relativeOrAbsolute(Path path, Path repoRoot) {
        if (path == null) {
            return ''
        }

        Path normalizedPath = path.toAbsolutePath().normalize()
        Path normalizedRoot = repoRoot.toAbsolutePath().normalize()
        if (normalizedPath.startsWith(normalizedRoot)) {
            return normalizeSeparators(normalizedRoot.relativize(normalizedPath).toString())
        }
        normalizeSeparators(normalizedPath.toString())
    }

    private static String formatUtc(Object value) {
        if (value == null) {
            return ''
        }

        if (value instanceof Instant) {
            return DateTimeFormatter.ISO_INSTANT.format(value as Instant)
        }

        if (value instanceof Date) {
            return DateTimeFormatter.ISO_INSTANT.format((value as Date).toInstant())
        }

        try {
            return DateTimeFormatter.ISO_INSTANT.format(OffsetDateTime.parse(value.toString()).withOffsetSameInstant(ZoneOffset.UTC))
        } catch (Exception ignored) {
            return value.toString()
        }
    }

    private static boolean hasFlag(String commandLine, String flag) {
        tokenize(commandLine).contains(flag)
    }

    private static String extractOption(String commandLine, List<String> optionNames) {
        List<String> tokens = tokenize(commandLine)
        for (int index = 0; index < tokens.size(); index++) {
            String token = tokens[index]
            if (optionNames.contains(token) && index + 1 < tokens.size()) {
                return tokens[index + 1]
            }
            String matchingPrefix = optionNames.find { String optionName -> token.startsWith("${optionName}=") }
            if (matchingPrefix) {
                return token.substring(matchingPrefix.length() + 1)
            }
        }
        null
    }

    private static List<String> tokenize(String commandLine) {
        if (!commandLine) {
            return []
        }

        List<String> tokens = []
        StringBuilder current = new StringBuilder()
        boolean singleQuoted = false
        boolean doubleQuoted = false
        boolean escaping = false

        for (int index = 0; index < commandLine.length(); index++) {
            char ch = commandLine.charAt(index)
            if (escaping) {
                current.append(ch)
                escaping = false
                continue
            }
            if (ch == '\\' && !singleQuoted) {
                escaping = true
                continue
            }
            if (ch == '\'' && !doubleQuoted) {
                singleQuoted = !singleQuoted
                continue
            }
            if (ch == '"' && !singleQuoted) {
                doubleQuoted = !doubleQuoted
                continue
            }
            if (Character.isWhitespace(ch) && !singleQuoted && !doubleQuoted) {
                if (current.length() > 0) {
                    tokens << current.toString()
                    current.setLength(0)
                }
                continue
            }
            current.append(ch)
        }

        if (current.length() > 0) {
            tokens << current.toString()
        }

        tokens
    }

    private static String normalizeSeparators(String value) {
        value.replace('\\', '/')
    }
}
