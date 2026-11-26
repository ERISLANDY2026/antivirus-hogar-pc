# grupo_openvpn.ps1 - Antivirus Hogar PC (v1.0.12; verificado en la v1.0.18)
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
#      de Win32_ComputerSystem.UserName, con respaldo al dueño
#      del proceso explorer.exe y por ultimo a USERNAME).
#   3. VERIFICA la pertenencia releyendo el grupo despues de
#      agregar (v1.0.18: no basta con que el comando no falle;
#      si la verificacion no lo ve, reintenta con
#      «net localgroup» y vuelve a verificar). El resultado
#      deja constancia de la verificacion, no solo del intento.
#   4. Verifica que el servicio OpenVPNServiceInteractive queda
#      corriendo y con arranque automatico (lo corrige si no).
# Deja el resultado, linea a linea y en ASCII, en el archivo de
# -Resultado; el instalador lo vuelca a openvpn-instalacion.txt.
# La pertenencia al grupo se aplica al INICIAR SESION: si el
# usuario fue agregado ahora, la app lo detecta y le dice que
# cierre sesion una vez.

param(
    [string]$Resultado = "grupo-openvpn-resultado.txt"
)

$lineas = @()
function Anotar([string]$texto) { $script:lineas += $texto }

function EsMiembro([string]$hoja) {
    try {
        $miembros = Get-LocalGroupMember -Group "OpenVPN Administrators" -ErrorAction Stop
        foreach ($m in $miembros) {
            if ((($m.Name -split '\\')[-1]) -ieq $hoja) { return $true }
        }
    } catch {}
    return $false
}

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
if (-not $objetivo) {
    # Respaldo: el dueño del explorer.exe de la sesion (el
    # instalador elevado puede correr con otra cuenta).
    try {
        $explorador = Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" -ErrorAction Stop | Select-Object -First 1
        if ($explorador) {
            $dueno = Invoke-CimMethod -InputObject $explorador -MethodName GetOwner -ErrorAction Stop
            if ($dueno -and $dueno.User) {
                $objetivo = if ($dueno.Domain) { "$($dueno.Domain)\$($dueno.User)" } else { $dueno.User }
            }
        }
    } catch {}
}
if (-not $objetivo) { $objetivo = $env:USERNAME }
$hoja = ($objetivo -split '\\')[-1]

# 3) Agregar y VERIFICAR (con reintento por net localgroup).
try {
    if (EsMiembro $hoja) {
        Anotar "Usuario ${hoja}: ya estaba en el grupo 'OpenVPN Administrators' (verificado)."
    } else {
        Add-LocalGroupMember -Group "OpenVPN Administrators" -Member $objetivo -ErrorAction Stop
        if (EsMiembro $hoja) {
            Anotar "Usuario ${hoja}: agregado al grupo 'OpenVPN Administrators' y VERIFICADO en la lista del grupo. La pertenencia se aplica al iniciar sesion: cierra sesion una vez para que la VPN use su via normal."
        } else {
            Anotar "Usuario ${hoja}: el alta no se reflejo en el grupo; reintentando con net localgroup."
            net localgroup "OpenVPN Administrators" $objetivo /add | Out-Null
            if (EsMiembro $hoja) {
                Anotar "Usuario ${hoja}: agregado con net localgroup y VERIFICADO en la lista del grupo. La pertenencia se aplica al iniciar sesion."
            } else {
                Anotar "Usuario ${hoja}: ERROR - no se pudo verificar su pertenencia al grupo tras dos vias."
            }
        }
    }
} catch {
    Anotar "Usuario ${hoja}: ERROR al agregarlo al grupo: $($_.Exception.Message)"
}

# 4) El servicio interactivo corriendo y automatico.
try {
    $svc = Get-Service -Name "OpenVPNServiceInteractive" -ErrorAction Stop
    Anotar "Servicio OpenVPNServiceInteractive: $($svc.Status), arranque $($svc.StartType)."
    if ($svc.StartType -eq "Disabled") {
        Set-Service -Name "OpenVPNServiceInteractive" -StartupType Automatic -ErrorAction Stop
        Anotar "Servicio OpenVPNServiceInteractive: arranque corregido a Automatico."
    }
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
