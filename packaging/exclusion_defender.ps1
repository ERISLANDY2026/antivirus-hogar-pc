# Antivirus Hogar PC — exclusión de Microsoft Defender (v1.0.7).
#
# Lo lanza el INSTALADOR (que ya corre como administrador) para que
# Defender no vuelva a borrar la app por falso positivo (ejecutable
# PyInstaller sin firmar: en la PC del usuario borró la 1.0.6).
#
# Alcance DECLARADO y mínimo: se excluyen SOLO las dos carpetas
# propias de la app — la de instalación y la de datos —. Nada más:
# ni procesos, ni extensiones, ni ninguna otra ruta del sistema.
# Después de añadirlas, se LEEN DE VUELTA (Get-MpPreference) y el
# resultado VERIFICADO se escribe en un JSON junto a la app: si la
# Protección contra alteraciones u otra política lo impidió, el
# JSON lo dice y la app avisa al abrir con el paso manual. Nunca se
# finge que la exclusión quedó puesta.
param(
    [Parameter(Mandatory = $true)][string]$AppDir,
    [Parameter(Mandatory = $true)][string]$DatosDir,
    [Parameter(Mandatory = $true)][string]$Resultado
)
$salida = [ordered]@{
    app        = $false
    datos      = $false
    ya_estaban = $false
    error      = ""
}
try {
    $antes = @((Get-MpPreference).ExclusionPath)
    $salida.ya_estaban = ($antes -contains $AppDir) -and ($antes -contains $DatosDir)
    Add-MpPreference -ExclusionPath $AppDir
    Add-MpPreference -ExclusionPath $DatosDir
    $despues = @((Get-MpPreference).ExclusionPath)
    $salida.app = ($despues -contains $AppDir)
    $salida.datos = ($despues -contains $DatosDir)
    if (-not ($salida.app -and $salida.datos)) {
        $salida.error = "La lectura de vuelta no muestra las dos exclusiones."
    }
}
catch {
    $salida.error = $_.Exception.Message
}
$salida | ConvertTo-Json | Set-Content -Path $Resultado -Encoding UTF8
