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
    $UpdaterPath = Join-Path $DistDirectory "KenjiUpdateInstaller.exe"
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "No se generó el ejecutable esperado: $ExecutablePath"
    }
    if (-not (Test-Path -LiteralPath $UpdaterPath)) {
        throw "No se generó el helper esperado: $UpdaterPath"
    }

    $Version = (& $PythonExecutable -c "from src.config import APP_VERSION; print(APP_VERSION)").Trim()
    $ZipPath = Join-Path $DistDirectory "KenjiMusicDownloader-v$Version-Windows-x64.zip"
    $ArchiveParameters = @{
        LiteralPath = @(
            $ExecutablePath,
            $UpdaterPath,
            (Join-Path $ProjectRoot "README.md")
        )
        DestinationPath = $ZipPath
        CompressionLevel = "Optimal"
        Force = $true
    }
    Compress-Archive @ArchiveParameters

    $ZipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
    $ManifestPath = Join-Path $DistDirectory "update.json"
    $Manifest = @{
        version = $Version
        assets = @{
            "windows-x64" = @{
                name = [System.IO.Path]::GetFileName($ZipPath)
                sha256 = $ZipHash
            }
        }
        notes = "Actualización de Kenji Music Downloader v$Version"
    } | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText(
        $ManifestPath,
        $Manifest,
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Host ""
    Write-Host "Empaquetado completado correctamente."
    Write-Host "Ejecutable: $ExecutablePath"
    Write-Host "Helper: $UpdaterPath"
    Write-Host "Paquete para GitHub Releases: $ZipPath"
    Write-Host "Manifest: $ManifestPath"
}
finally {
    Pop-Location
}
