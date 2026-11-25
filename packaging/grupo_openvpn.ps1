# grupo_openvpn.ps1 - Antivirus Hogar PC v1.0.12
#
# Lo ejecuta el instalador (como administrador) tras instalar
# OpenVPN. El OpenVPN Interactive Service solo acepta perfiles
# fuera de su carpeta de configuracion si el usuario es
# administrador o pertenece al grupo local "OpenVPN
# Administrators"; los perfiles de la app viven en
# %LOCALAPPDATA%\AntivirusHogarPC\vpn, asi que sin este grupo el
# servicio rechazaria cada conexion. Este script:
#   1. Crea el grupo local "OpenVPN Administrators" si falta.
#   2. Agrega al usuario de la sesion interactiva (el instalador
#      corre elevado y puede ser OTRA cuenta: el objetivo sale
#      de Win32_ComputerSystem.UserName, con respaldo a USERNAME).
#   3. Verifica que el servicio OpenVPNServiceInteractive queda
#      corriendo (lo arranca si esta parado).
# Deja el resultado, linea a linea y en ASCII, en el archivo de
# -Resultado; el instalador lo vuelca a openvpn-instalacion.txt.
# La pertenencia al grupo se aplica al INICIAR SESION: si el
# usuario fue agregado ahora, la app lo detecta y le dice que
# cierre sesion una vez (mientras tanto conecta elevada).

param(
    [string]$Resultado = "grupo-openvpn-resultado.txt"
)

$lineas = @()
function Anotar([string]$texto) { $script:lineas += $texto }

# 1) El grupo local.
try {
    $grupo = Get-LocalGroup -Name "OpenVPN Administrators" -ErrorAction SilentlyContinue
    if (-not $grupo) {
        New-LocalGroup -Name "OpenVPN Administrators" -Description "Usuarios autorizados a usar el OpenVPN Interactive Service con perfiles fuera de su carpeta." | Out-Null
        Anotar "Grupo 'OpenVPN Administrators': creado."
    } else {
        Anotar "Grupo 'OpenVPN Administrators': ya existia."
    }
} catch {
    Anotar "Grupo 'OpenVPN Administrators': ERROR al comprobarlo/crearlo: $($_.Exception.Message)"
}

# 2) El usuario de la sesion interactiva.
$objetivo = ""
try { $objetivo = (Get-CimInstance Win32_ComputerSystem).UserName } catch {}
if (-not $objetivo) { $objetivo = $env:USERNAME }
$hoja = ($objetivo -split '\\')[-1]
try {
    $miembros = Get-LocalGroupMember -Group "OpenVPN Administrators" -ErrorAction Stop
    $ya = $false
    foreach ($m in $miembros) {
        if ((($m.Name -split '\\')[-1]) -ieq $hoja) { $ya = $true }
    }
    if ($ya) {
        Anotar "Usuario ${hoja}: ya estaba en el grupo 'OpenVPN Administrators'."
    } else {
        Add-LocalGroupMember -Group "OpenVPN Administrators" -Member $objetivo -ErrorAction Stop
        Anotar "Usuario ${hoja}: agregado al grupo 'OpenVPN Administrators'. La pertenencia se aplica al iniciar sesion: cierra sesion una vez para que la VPN use su via normal."
    }
} catch {
    Anotar "Usuario ${hoja}: ERROR al agregarlo al grupo: $($_.Exception.Message)"
}

# 3) El servicio interactivo corriendo.
try {
    $svc = Get-Service -Name "OpenVPNServiceInteractive" -ErrorAction Stop
    Anotar "Servicio OpenVPNServiceInteractive: $($svc.Status)."
    if ($svc.Status -ne "Running") {
        Start-Service -Name "OpenVPNServiceInteractive" -ErrorAction Stop
        $svc = Get-Service -Name "OpenVPNServiceInteractive"
        Anotar "Servicio OpenVPNServiceInteractive tras arrancarlo: $($svc.Status)."
    }
} catch {
    Anotar "Servicio OpenVPNServiceInteractive: ERROR: $($_.Exception.Message)"
}

try {
    Set-Content -Path $Resultado -Value $lineas -Encoding ASCII
} catch {}
$lineas
