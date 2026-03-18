"use strict";

const cp = require("child_process");
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");

let extensionBasePath = "";

const CLI_MAP = {
  mirror: {
    command: "codex-session-mirror",
    module: "codex_portable_context.cli.mirror",
  },
  list: {
    command: "codex-session-list",
    module: "codex_portable_context.cli.list",
  },
  open: {
    command: "codex-session-open",
    module: "codex_portable_context.cli.open",
  },
  latest: {
    command: "codex-session-latest",
    module: "codex_portable_context.cli.latest",
  },
  handoff: {
    command: "codex-session-handoff",
    module: "codex_portable_context.cli.handoff",
  },
};

function activate(context) {
  extensionBasePath = context.extensionPath;
  context.subscriptions.push(
    registerManagedCommand("codexPortableContext.exportMirror", exportMirror),
    registerManagedCommand("codexPortableContext.generateHandoff", generateHandoff),
    registerManagedCommand("codexPortableContext.openLatestReader", openLatestReader),
    registerManagedCommand("codexPortableContext.openLatestHandoff", openLatestHandoff),
    registerManagedCommand("codexPortableContext.openSessionReader", openSessionReader),
    registerManagedCommand("codexPortableContext.openSessionMarkdown", openSessionMarkdown),
  );
}

function deactivate() {}

function registerManagedCommand(commandName, handler) {
  return vscode.commands.registerCommand(commandName, async () => {
    try {
      await handler();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      await vscode.window.showErrorMessage(message);
    }
  });
}

async function exportMirror() {
  const workingDirectory = getWorkingDirectory();
  const outDir = getOutDir(workingDirectory);
  const exportMode = await pickExportMode();
  if (!exportMode) {
    return;
  }

  const exportResult = await withCliProgress("Exporting Codex portable mirror", async () => {
    const args = ["--out-dir", outDir];
    if (exportMode.redacted) {
      args.push("--redact");
    }
    args.push("--json");
    const stdout = await runCli("mirror", args, workingDirectory);
    return parseJsonOutput(stdout, "codex-session-mirror --json");
  });

  const action = await vscode.window.showInformationMessage(
    `Mirror export complete: ${exportResult.session_count} sessions in ${exportResult.out_dir}`,
    "Open Landing",
    "Open Latest Reader",
  );
  if (action === "Open Landing") {
    await openArtifactPath(exportResult.reader_index_path);
  } else if (action === "Open Latest Reader") {
    await openResolvedArtifact("open", ["--out-dir", outDir, "--latest", "--reader", "--print"], workingDirectory);
  }
}

async function generateHandoff() {
  const workingDirectory = getWorkingDirectory();
  const outDir = getOutDir(workingDirectory);
  const handoffPath = await withCliProgress("Generating latest handoff", async () => {
    const stdout = await runCli("handoff", ["--out-dir", outDir, "--latest", "--print"], workingDirectory);
    return stdout.trim();
  });
  await openArtifactPath(handoffPath);
}

async function openLatestReader() {
  const workingDirectory = getWorkingDirectory();
  const outDir = getOutDir(workingDirectory);
  await openResolvedArtifact("open", ["--out-dir", outDir, "--latest", "--reader", "--print"], workingDirectory);
}

async function openLatestHandoff() {
  const workingDirectory = getWorkingDirectory();
  const outDir = getOutDir(workingDirectory);
  await openResolvedArtifact("open", ["--out-dir", outDir, "--latest", "--handoff", "--print"], workingDirectory);
}

async function openSessionReader() {
  const selection = await selectSession();
  if (!selection) {
    return;
  }
  await openResolvedArtifact(
    "open",
    ["--out-dir", selection.outDir, selection.sessionId, "--reader", "--print"],
    selection.workingDirectory,
  );
}

async function openSessionMarkdown() {
  const selection = await selectSession();
  if (!selection) {
    return;
  }
  await openResolvedArtifact(
    "open",
    ["--out-dir", selection.outDir, selection.sessionId, "--print"],
    selection.workingDirectory,
  );
}

async function selectSession() {
  const workingDirectory = getWorkingDirectory();
  const outDir = getOutDir(workingDirectory);
  const stdout = await withCliProgress("Loading exported sessions", async () =>
    runCli("list", ["--out-dir", outDir, "--json"], workingDirectory),
  );
  const entries = JSON.parse(stdout);
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new Error("No exported sessions are available in the current mirror.");
  }

  const items = entries.map((entry) => ({
    label: entry.title || entry.session_id,
    description: entry.summary_line || entry.session_id,
    detail: entry.activity_line || entry.environment_line || "",
    sessionId: entry.session_id,
  }));

  const selected = await vscode.window.showQuickPick(items, {
    matchOnDescription: true,
    matchOnDetail: true,
    placeHolder: "Choose an exported session",
  });
  if (!selected) {
    return null;
  }

  return {
    workingDirectory,
    outDir,
    sessionId: selected.sessionId,
  };
}

async function openResolvedArtifact(kind, args, workingDirectory) {
  const stdout = await withCliProgress("Resolving artifact", async () =>
    runCli(kind, args, workingDirectory),
  );
  await openArtifactPath(stdout.trim());
}

async function openArtifactPath(targetPath) {
  if (!targetPath) {
    throw new Error("The CLI did not return a target path.");
  }

  const resolvedPath = path.resolve(targetPath);
  const uri = vscode.Uri.file(resolvedPath);
  if (resolvedPath.toLowerCase().endsWith(".html")) {
    await vscode.env.openExternal(uri);
    return;
  }

  const document = await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(document, { preview: false });
}

async function pickExportMode() {
  const config = getConfig();
  const preferRedacted = config.get("preferRedactedExport", false);
  const items = [
    {
      label: preferRedacted ? "Redacted export (Recommended)" : "Standard export (Recommended)",
      redacted: preferRedacted,
    },
    {
      label: preferRedacted ? "Standard export" : "Redacted export",
      redacted: !preferRedacted,
    },
  ];
  return vscode.window.showQuickPick(items, {
    placeHolder: "Choose the export mode",
  });
}

async function withCliProgress(title, action) {
  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title,
    },
    action,
  );
}

function parseJsonOutput(stdout, label) {
  try {
    return JSON.parse(stdout);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${label} returned invalid JSON: ${detail}`);
  }
}

function getConfig() {
  return vscode.workspace.getConfiguration("codexPortableContext");
}

function getWorkingDirectory() {
  const config = getConfig();
  const configured = config.get("workingDirectory", "").trim();
  if (configured) {
    return resolvePath(configured, fallbackWorkspaceRoot());
  }

  const workspaceRoot = fallbackWorkspaceRoot();
  if (!workspaceRoot) {
    throw new Error(
      "No workspace folder is open. Open a workspace or set codexPortableContext.workingDirectory.",
    );
  }
  return workspaceRoot;
}

function getOutDir(workingDirectory) {
  const configured = getConfig().get("outDir", "./out");
  return resolvePath(configured, workingDirectory);
}

function fallbackWorkspaceRoot() {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  return folder ? folder.uri.fsPath : "";
}

function resolvePath(value, baseDirectory) {
  if (!value) {
    return baseDirectory;
  }
  if (path.isAbsolute(value)) {
    return value;
  }
  if (!baseDirectory) {
    return value;
  }
  return path.resolve(baseDirectory, value);
}

function resolveInvocation(kind, workingDirectory) {
  const spec = CLI_MAP[kind];
  if (!spec) {
    throw new Error(`Unsupported CLI kind: ${kind}`);
  }
  const attempts = [];

  const configuredDir = getConfig().get("commandDirectory", "").trim();
  if (configuredDir) {
    for (const directory of resolveConfiguredPathCandidates(configuredDir, workingDirectory)) {
      attempts.push(path.join(directory, executableName(spec.command)));
      const configuredCommand = resolveCommandFromDirectory(spec.command, directory);
      if (configuredCommand) {
        return { command: configuredCommand, args: [], attempts };
      }
    }
  }

  const localScripts = localScriptsDirectory(workingDirectory);
  if (localScripts) {
    attempts.push(path.join(localScripts, executableName(spec.command)));
  }
  const localCommand = resolveCommandFromDirectory(spec.command, localScripts);
  if (localCommand) {
    return { command: localCommand, args: [], attempts };
  }

  const configuredPython = getConfig().get("pythonPath", "").trim();
  if (configuredPython) {
    for (const candidate of resolveConfiguredPathCandidates(configuredPython, workingDirectory)) {
      attempts.push(`${candidate} -m ${spec.module}`);
      if (fs.existsSync(candidate)) {
        return {
          command: candidate,
          args: ["-m", spec.module],
          attempts,
        };
      }
    }
  }

  const localPython = localPythonInterpreter(workingDirectory);
  if (localPython) {
    attempts.push(`${localPython} -m ${spec.module}`);
    return {
      command: localPython,
      args: ["-m", spec.module],
      attempts,
    };
  }

  attempts.push(spec.command);
  return { command: spec.command, args: [], attempts };
}

function resolveConfiguredPathCandidates(value, workingDirectory) {
  if (!value) {
    return [];
  }
  if (path.isAbsolute(value)) {
    return [value];
  }

  const candidates = [];
  for (const baseDirectory of resolutionBaseDirectories(workingDirectory)) {
    const resolved = path.resolve(baseDirectory, value);
    if (!candidates.includes(resolved)) {
      candidates.push(resolved);
    }
  }
  return candidates.length > 0 ? candidates : [value];
}

function resolutionBaseDirectories(workingDirectory) {
  const directories = [];
  const workspaceRoot = fallbackWorkspaceRoot();
  if (workspaceRoot) {
    directories.push(workspaceRoot);
  }
  if (extensionBasePath && !directories.includes(extensionBasePath)) {
    directories.push(extensionBasePath);
  }
  if (workingDirectory && !directories.includes(workingDirectory)) {
    directories.push(workingDirectory);
  }
  return directories;
}

function executableName(commandName) {
  return process.platform === "win32" ? `${commandName}.exe` : commandName;
}

function resolveCommandFromDirectory(commandName, directory) {
  if (!directory) {
    return "";
  }
  const filename = executableName(commandName);
  const fullPath = path.join(directory, filename);
  return fs.existsSync(fullPath) ? fullPath : "";
}

function localScriptsDirectory(workingDirectory) {
  if (!workingDirectory) {
    return "";
  }
  return path.join(workingDirectory, ".venv", process.platform === "win32" ? "Scripts" : "bin");
}

function localPythonInterpreter(workingDirectory) {
  if (!workingDirectory) {
    return "";
  }
  const scriptsDirectory = localScriptsDirectory(workingDirectory);
  const filename = process.platform === "win32" ? "python.exe" : "python";
  const fullPath = path.join(scriptsDirectory, filename);
  return fs.existsSync(fullPath) ? fullPath : "";
}

async function runCli(kind, args, workingDirectory) {
  const invocation = resolveInvocation(kind, workingDirectory);
  return new Promise((resolve, reject) => {
    cp.execFile(
      invocation.command,
      [...invocation.args, ...args],
      {
        cwd: workingDirectory || undefined,
        windowsHide: true,
        maxBuffer: 10 * 1024 * 1024,
      },
      (error, stdout, stderr) => {
        if (!error) {
          resolve(stdout);
          return;
        }

        if (error.code === "ENOENT") {
          const attempted = invocation.attempts && invocation.attempts.length
            ? ` Tried: ${invocation.attempts.join(" | ")}`
            : "";
          reject(
            new Error(
              [
                `Could not find a usable ${CLI_MAP[kind].command} invocation.`,
                "Bootstrap the project environment or configure codexPortableContext.commandDirectory / codexPortableContext.pythonPath.",
                attempted,
              ].join(" "),
            ),
          );
          return;
        }

        const detail = [stderr, stdout, error.message].filter(Boolean).join("\n").trim();
        reject(new Error(detail || `${CLI_MAP[kind].command} failed.`));
      },
    );
  });
}

module.exports = {
  activate,
  deactivate,
};
