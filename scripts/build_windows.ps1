[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExecutable = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "kenji-music-downloader.spec"
$BuildDirectory = Join-Path $ProjectRoot "build"
$DistDirectory = Join-Path $ProjectRoot "dist"

function Remove-SafeBuildDirectory {
    param([Parameter(Mandatory = $true)][string]$TargetPath)

    $ResolvedTarget = [System.IO.Path]::GetFullPath($TargetPath)
    $RootPrefix = $ProjectRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar

    if (-not $ResolvedTarget.StartsWith(
        $RootPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Se rechazó una ruta de limpieza fuera del proyecto: $ResolvedTarget"
    }

    if (Test-Path -LiteralPath $ResolvedTarget) {
        Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "No se encontró el entorno virtual: $PythonExecutable"
}

foreach ($ToolName in @("ffmpeg", "ffprobe")) {
    if (-not (Get-Command $ToolName -ErrorAction SilentlyContinue)) {
        throw "No se encontró $ToolName en PATH. Instala FFmpeg antes de empaquetar."
    }
}

Push-Location $ProjectRoot
try {
    if (-not $SkipTests) {
        & $PythonExecutable -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) {
            throw "Las pruebas fallaron. Se canceló el empaquetado."
        }
    }

    Remove-SafeBuildDirectory -TargetPath $BuildDirectory
    Remove-SafeBuildDirectory -TargetPath $DistDirectory

    & $PythonExecutable -m PyInstaller --clean --noconfirm $SpecFile
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller terminó con código $LASTEXITCODE."
    }

    $ExecutablePath = Join-Path $DistDirectory "KenjiMusicDownloader.exe"
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "No se generó el ejecutable esperado: $ExecutablePath"
    }

    $Version = (& $PythonExecutable -c "from src.config import APP_VERSION; print(APP_VERSION)").Trim()
    $ZipPath = Join-Path $DistDirectory "KenjiMusicDownloader-v$Version-Windows-x64.zip"
    $ArchiveParameters = @{
        LiteralPath = @($ExecutablePath, (Join-Path $ProjectRoot "README.md"))
        DestinationPath = $ZipPath
        CompressionLevel = "Optimal"
        Force = $true
    }
    Compress-Archive @ArchiveParameters

    Write-Host ""
    Write-Host "Empaquetado completado correctamente."
    Write-Host "Ejecutable: $ExecutablePath"
    Write-Host "Paquete para GitHub Releases: $ZipPath"
}
finally {
    Pop-Location
}
