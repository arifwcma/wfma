#!/usr/bin/env bash
# lizmap_diag.sh - diagnose Lizmap + QGIS Server setup
# Output to /tmp/lizmap_diag.txt
set -u

OUT="/tmp/lizmap_diag.txt"
exec >"$OUT" 2>&1

section() { printf "\n\n===== %s =====\n" "$1"; }
run() { local cmd="$*"; echo; echo "+ $cmd"; eval "$cmd"; echo "exit_code=$?"; }

section "LIZMAP CONFIG: localconfig.ini.php"
run "cat /var/www/lizmap-web-client-3.9.1/lizmap/var/config/localconfig.ini.php"

section "LIZMAP CONFIG: lizmapConfig.ini.php"
run "cat /var/www/lizmap-web-client-3.9.1/lizmap/var/config/lizmapConfig.ini.php"

section "LIZMAP CONFIG: profiles.ini.php"
run "cat /var/www/lizmap-web-client-3.9.1/lizmap/var/config/profiles.ini.php"

section "LIZMAP CONFIG DIST: localconfig.ini.php.dist"
run "cat /var/www/lizmap-web-client-3.9.1/lizmap/var/config/localconfig.ini.php.dist"

section "QGIS PROJECT FILES"
run "ls -la /var/www/qgis/wfml/"
run "ls -la /var/www/qgis/wfml/wfml.qgs*"
run "stat /var/www/qgis/wfml/wfml.qgs"

section "QGIS PROJECT PERMISSIONS (www-data readable?)"
run "sudo -u www-data test -r /var/www/qgis/wfml/wfml.qgs && echo 'READABLE' || echo 'NOT READABLE'"
run "sudo -u www-data test -r /var/www/qgis/wfml/wfml.qgs.cfg && echo 'READABLE' || echo 'NOT READABLE'"

section "LIZMAP INSTANCES"
run "ls -la /var/www/lizmap-web-client-3.9.1/lizmap/var/config/"
run "find /var/www/lizmap-web-client-3.9.1/ -name 'repositories.ini.php' -exec cat {} \;"

section "LIZMAP VAR PERMISSIONS"
run "ls -la /var/www/lizmap-web-client-3.9.1/lizmap/var/"
run "ls -la /var/www/lizmap-web-client-3.9.1/lizmap/var/db/"
run "ls -la /var/www/lizmap-web-client-3.9.1/lizmap/var/log/"

section "APACHE QGIS SERVER CONFIG"
run "cat /etc/apache2/sites-available/qgis-server.conf"
run "cat /etc/apache2/ports.conf"

section "APACHE ENABLED SITES"
run "ls -la /etc/apache2/sites-enabled/"

section "APACHE MODULES"
run "apache2ctl -M 2>/dev/null | grep -E 'fcgid|cgi'"

section "NGINX TESTPOZI CONFIG"
run "cat /etc/nginx/sites-available/testpozi.online"

section "QGIS SERVER PLUGIN"
run "ls -laR /usr/lib/qgis/plugins/"
run "dpkg -l | grep -i qgis"
run "dpkg -l | grep -i python3-qgis"

section "QGIS SERVER VERSION"
run "/usr/lib/cgi-bin/qgis_mapserv.fcgi --version 2>&1 || true"

section "WMS GETCAPABILITIES (direct via Apache)"
run "wget -qO- 'http://127.0.0.1:8080/cgi-bin/qgis_mapserv.fcgi?SERVICE=WMS&REQUEST=GetCapabilities&MAP=/var/www/qgis/wfml/wfml.qgs' | head -30"

section "LIZMAP SERVER PLUGIN ENDPOINT"
run "wget -qO- 'http://127.0.0.1:8080/cgi-bin/qgis_mapserv.fcgi/lizmap/server.json'"
run "wget -qO- 'http://127.0.0.1:8080/cgi-bin/qgis_mapserv.fcgi?SERVICE=LIZMAP&REQUEST=GetServerSettings'"

section "QGIS SERVER LOGS"
run "tail -50 /var/log/apache2/qgis-error.log 2>/dev/null || echo 'no log'"
run "tail -50 /var/log/apache2/qgis-access.log 2>/dev/null | tail -20"

section "LIZMAP ERROR LOGS"
run "tail -50 /var/www/lizmap-web-client-3.9.1/lizmap/var/log/errors.log 2>/dev/null || echo 'no log'"
run "tail -30 /var/www/lizmap-web-client-3.9.1/lizmap/var/log/lizmap-admin.log 2>/dev/null || echo 'no log'"

section "PHP-FPM STATUS"
run "systemctl status php8.3-fpm --no-pager"
run "php -v"

section "SERVICES STATUS"
run "systemctl is-active apache2 nginx php8.3-fpm"
run "sudo ss -tlnp | grep -E '80|8080|443'"

section "DISK AND MEMORY"
run "df -h /"
run "free -h"

echo ""
echo "===== DONE ====="
