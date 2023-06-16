[CmdletBinding()]
Param(
    [ValidateSet('All', 'fb30', 'fb40', 'fb50')] 
    [System.String[]]
    $Engines = 'All',

    [Switch]
    $Force
)

$rootFolder = Join-Path $env:TEMP 'firebird-driver-tests'

if ($Force) {
    Remove-Item -Path $rootFolder -Force -Recurse -ErrorAction SilentlyContinue
    mkdir $rootFolder | Out-Null
}

$binariesExist = Test-Path "$rootFolder/fb30/fbclient.dll"
if ($Force -or (-not $binariesExist)) {
    Write-Verbose 'Downloading Firebird binaries...'

    Remove-Item -Path $rootFolder -Force -Recurse -ErrorAction SilentlyContinue
    mkdir $rootFolder | Out-Null

    git clone --quiet --depth 1 --single-branch https://github.com/fdcastel/firebird-binaries $rootFolder
}

$DbPrefix='firebird-driver'
$fbkFile = Join-Path $PSScriptRoot './test/fbtest30-src.fbk'

# Build databases
if ($Engines -eq 'All') {
    $Engines = 'fb30', 'fb40', 'fb50'
}
$Engines | ForEach-Object {
    $engine = $_

    $engineFolder = Join-Path $rootFolder $engine
    $gbak = Join-Path $engineFolder 'gbak.exe'

    $database = Join-Path $rootFolder "$DbPrefix.$engine.fdb"
    Remove-Item $database -Force -ErrorAction SilentlyContinue

    Write-Verbose "Creating '$database'..."
    & $gbak -c $fbkFile $database 
}
