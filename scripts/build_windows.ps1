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
$ReleaseDirectory = Join-Path $ProjectRoot "release\windows"

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

function Resolve-BuildToolExecutable {
    param([Parameter(Mandatory = $true)][string]$ToolName)

    $PreferredDirectory = [Environment]::GetEnvironmentVariable("YUGEN_FFMPEG_DIR")
    if (-not [string]::IsNullOrWhiteSpace($PreferredDirectory)) {
        foreach ($CandidateName in @("$ToolName.exe", $ToolName)) {
            $CandidatePath = Join-Path $PreferredDirectory $CandidateName
            if (Test-Path -LiteralPath $CandidatePath -PathType Leaf) {
                return (Resolve-Path -LiteralPath $CandidatePath).Path
            }
        }
    }

    foreach ($CandidateName in @("$ToolName.exe", $ToolName)) {
        $Command = Get-Command $CandidateName -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $Command) {
            return $Command.Source
        }
    }

    throw (
        "No se encontró {0}. Instala FFmpeg o define YUGEN_FFMPEG_DIR con ffmpeg.exe y ffprobe.exe." -f
        $ToolName
    )
}

function Copy-RequiredFfmpegTools {
    param([Parameter(Mandatory = $true)][string]$DestinationDirectory)

    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
    foreach ($ToolName in @("ffmpeg", "ffprobe")) {
        $SourcePath = Resolve-BuildToolExecutable -ToolName $ToolName
        $DestinationPath = Join-Path $DestinationDirectory "$ToolName.exe"
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
        if (-not (Test-Path -LiteralPath $DestinationPath -PathType Leaf)) {
            throw "No se pudo copiar $ToolName a $DestinationPath"
        }
        Write-Host "Herramienta incluida: $DestinationPath"
        Copy-OptionalFfmpegNotices -SourcePath $SourcePath -DestinationDirectory $DestinationDirectory
    }
}

function Copy-OptionalFfmpegNotices {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationDirectory
    )

    $BinaryDirectory = Split-Path -Parent $SourcePath
    $CandidateDirectories = @(
        $BinaryDirectory,
        (Split-Path -Parent $BinaryDirectory)
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

    foreach ($Directory in $CandidateDirectories) {
        foreach ($NoticeName in @("LICENSE", "COPYING", "README.txt")) {
            $NoticePath = Join-Path $Directory $NoticeName
            if (-not (Test-Path -LiteralPath $NoticePath -PathType Leaf)) {
                continue
            }
            $DestinationName = "FFmpeg-{0}.txt" -f [System.IO.Path]::GetFileNameWithoutExtension($NoticeName)
            $DestinationPath = Join-Path $DestinationDirectory $DestinationName
            if (-not (Test-Path -LiteralPath $DestinationPath -PathType Leaf)) {
                Copy-Item -LiteralPath $NoticePath -Destination $DestinationPath -Force
                Write-Host "Aviso de FFmpeg incluido: $DestinationPath"
            }
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
            "YugenAudio.exe",
            "YugenAudioUpdateInstaller.exe",
            "update-windows.json",
            "update.json"
        ) -or $_.Name -like "YugenAudio-v*-Windows-x64.zip" -or $_.Name -like "KenjiMusicDownloader-v*-Windows-x64.zip"
    } | Remove-Item -Force
    Get-ChildItem -LiteralPath $DistDirectory -Directory | Where-Object {
        $_.Name -eq "KenjiMusicDownloader" -or
        $_.Name -like "YugenAudio-v*-Windows-x64" -or
        $_.Name -like "KenjiMusicDownloader-v*-Windows-x64"
    } | ForEach-Object {
        Remove-SafeBuildDirectory -TargetPath $_.FullName
    }
    $OnedirOutput = Join-Path $DistDirectory "YugenAudio"
    if (Test-Path -LiteralPath $OnedirOutput) {
        Remove-SafeBuildDirectory -TargetPath $OnedirOutput
    }
    Remove-SafeBuildDirectory -TargetPath $ReleaseDirectory
    New-Item -ItemType Directory -Path $ReleaseDirectory | Out-Null

    & $PythonExecutable -m PyInstaller --clean --noconfirm $SpecFile
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller terminó con código $LASTEXITCODE."
    }

    $ExecutablePath = Join-Path $OnedirOutput "YugenAudio.exe"
    $UpdaterPath = Join-Path $OnedirOutput "YugenAudioUpdateInstaller.exe"
    if (-not (Test-Path -LiteralPath $ExecutablePath)) {
        throw "No se generó el ejecutable esperado: $ExecutablePath"
    }
    if (-not (Test-Path -LiteralPath $UpdaterPath)) {
        throw "No se generó el helper esperado: $UpdaterPath"
    }
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") `
        -Destination (Join-Path $OnedirOutput "README.md") -Force
    Copy-RequiredFfmpegTools -DestinationDirectory (Join-Path $OnedirOutput "tools")

    $ZipPath = Join-Path $DistDirectory "YugenAudio-v$Version-Windows-x64.zip"
    Compress-ArchiveWithRetry -SourcePath $OnedirOutput -DestinationPath $ZipPath

    & $PythonExecutable scripts\generate_update_manifest.py
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron generar los manifests de actualización."
    }
    $PlatformManifestPath = Join-Path $DistDirectory "update-windows.json"
    $CombinedManifestPath = Join-Path $DistDirectory "update.json"
    Copy-Item -LiteralPath $ZipPath -Destination $ReleaseDirectory -Force
    Copy-Item -LiteralPath $PlatformManifestPath -Destination $ReleaseDirectory -Force
    if (Test-Path -LiteralPath $CombinedManifestPath) {
        Copy-Item -LiteralPath $CombinedManifestPath -Destination $ReleaseDirectory -Force
    }

    Write-Host ""
    Write-Host "Empaquetado completado correctamente."
    Write-Host "Ejecutable: $ExecutablePath"
    Write-Host "Helper: $UpdaterPath"
    Write-Host "Paquete para GitHub Releases: $ZipPath"
    Write-Host "Manifest Windows: $PlatformManifestPath"
    Write-Host "Release Windows: $ReleaseDirectory"
    if (Test-Path -LiteralPath $CombinedManifestPath) {
        Write-Host "Manifest combinado: $CombinedManifestPath"
    }
}
finally {
    Pop-Location
}
