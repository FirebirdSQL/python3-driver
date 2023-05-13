[CmdletBinding()]
Param(
    [ValidateSet('fb30', 'fb40', 'fb50')] 
    [System.String[]]
    $Engine = 'fb50')

$rootFolder = Join-Path $env:TEMP 'firebird-driver-tests'

@"
FBTEST_CLIENT_LIBRARY=%TEMP%/firebird-driver-tests/$($Engine)/fbclient.dll
FBTEST_DATABASE=%TEMP%/firebird-driver-tests/FIREBIRD-DRIVER.$($Engine.ToUpper()).FDB
"@ | Out-File ./test/environment.txt -Encoding ascii
