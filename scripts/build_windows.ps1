[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $PythonExecutable = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}
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

function Compress-ArchiveWithRetry {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [int]$Attempts = 5,
        [int]$DelaySeconds = 2
    )

    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            Compress-Archive `
                -LiteralPath $SourcePath `
                -DestinationPath $DestinationPath `
                -CompressionLevel Optimal `
                -Force
            return
        }
        catch {
            if ($Attempt -ge $Attempts) {
                throw
            }

            Write-Warning (
                "No se pudo crear el ZIP en el intento {0}/{1}: {2}. Reintentando en {3}s..." -f
                $Attempt,
                $Attempts,
                $_.Exception.Message,
                $DelaySeconds
            )
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    throw "No se encontró el entorno virtual: $PythonExecutable"
}

Push-Location $ProjectRoot
try {
    $Version = (& $PythonExecutable -c "from src.config import APP_VERSION; print(APP_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
        throw "No se pudo leer APP_VERSION."
    }

    if (-not $SkipTests) {
        & $PythonExecutable -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) {
            throw "Las pruebas fallaron. Se canceló el empaquetado."
        }
    }

    Remove-SafeBuildDirectory -TargetPath $BuildDirectory
    if (-not (Test-Path -LiteralPath $DistDirectory)) {
        New-Item -ItemType Directory -Path $DistDirectory | Out-Null
    }
    # Limpia solo artefactos Windows; conserva un TAR.GZ Linux ya copiado a dist.
    Get-ChildItem -LiteralPath $DistDirectory -File | Where-Object {
        $_.Name -in @(
            "KenjiMusicDownloader.exe",
            "KenjiUpdateInstaller.exe",
            "update-windows.json",
            "update.json"
        ) -or $_.Name -like "KenjiMusicDownloader-v*-Windows-x64.zip"
    } | Remove-Item -Force
    Get-ChildItem -LiteralPath $DistDirectory -Directory | Where-Object {
        $_.Name -like "KenjiMusicDownloader-v*-Windows-x64"
    } | ForEach-Object {
        Remove-SafeBuildDirectory -TargetPath $_.FullName
    }
    $OnedirOutput = Join-Path $DistDirectory "KenjiMusicDownloader"
    if (Test-Path -LiteralPath $OnedirOutput) {
        Remove-SafeBuildDirectory -TargetPath $OnedirOutput
    }

    & $PythonExecutable -m PyInstaller --clean --noconfirm $SpecFile
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller terminó con código $LASTEXITCODE."
    }

    $ExecutablePath = Join-Path $OnedirOutput "KenjiMusicDownloader.exe"
    $UpdaterPath = Join-Path $OnedirOutput "KenjiUpdateInstaller.exe"
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "No se generó el ejecutable esperado: $ExecutablePath"
    }
    if (-not (Test-Path -LiteralPath $UpdaterPath)) {
        throw "No se generó el helper esperado: $UpdaterPath"
    }
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") `
        -Destination (Join-Path $OnedirOutput "README.md") -Force

    $ZipPath = Join-Path $DistDirectory "KenjiMusicDownloader-v$Version-Windows-x64.zip"
    Compress-ArchiveWithRetry -SourcePath $OnedirOutput -DestinationPath $ZipPath

    & $PythonExecutable scripts\generate_update_manifest.py
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron generar los manifests de actualización."
    }
    $PlatformManifestPath = Join-Path $DistDirectory "update-windows.json"
    $CombinedManifestPath = Join-Path $DistDirectory "update.json"

    Write-Host ""
    Write-Host "Empaquetado completado correctamente."
    Write-Host "Ejecutable: $ExecutablePath"
    Write-Host "Helper: $UpdaterPath"
    Write-Host "Paquete para GitHub Releases: $ZipPath"
    Write-Host "Manifest Windows: $PlatformManifestPath"
    if (Test-Path -LiteralPath $CombinedManifestPath) {
        Write-Host "Manifest combinado: $CombinedManifestPath"
    }
}
finally {
    Pop-Location
}
