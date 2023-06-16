[CmdletBinding()]
Param(
    [Parameter(ParameterSetName = 'Default')]
    [Alias("Local")]
    [Switch]
    $Default,

    [Parameter(ParameterSetName = 'Embedded')]
    [Alias("Engine")]
    [ValidateSet('fb30', 'fb40', 'fb50')] 
    [System.String[]]
    $Embedded = 'fb50'
)

$environmentFile = './test/environment.txt'
if ($Default) {
    # Use default environment (locally installed Firebird). Clear all environment variables.
    $env:FBTEST_CLIENT_LIBRARY=
    $env:FBTEST_DATABASE=

    Remove-Item $environmentFile -ErrorAction SilentlyContinue
} else {
    # Use embedded environment (Firebird embedded and database in TEMP subfolder)
    $env:FBTEST_CLIENT_LIBRARY="$($env:TEMP)/firebird-driver-tests/$($Embedded)/fbclient.dll"
    $env:FBTEST_DATABASE="$($env:TEMP)/firebird-driver-tests/FIREBIRD-DRIVER.$($Embedded.ToUpper()).FDB"

    @"
    FBTEST_CLIENT_LIBRARY=%TEMP%/firebird-driver-tests/$($Embedded)/fbclient.dll
    FBTEST_DATABASE=%TEMP%/firebird-driver-tests/FIREBIRD-DRIVER.$($Embedded.ToUpper()).FDB
"@ | Out-File $environmentFile -Encoding ascii
}
