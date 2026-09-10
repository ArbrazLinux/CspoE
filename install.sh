#!/usr/bin/env bash
# CspoE is developped and maintained by BreizhStakePool.io 
#
# Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
# Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
# donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
#
# Consider delegate your voting power to our Breizh DRep [BZH] 
# drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h

set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_FILE="$SOURCE_ROOT/CspoE.conf"
MODE="${1:---check}"

conf_value() {
    local key="$1"
    awk -v wanted="$key" '
        BEGIN { single_quote = sprintf("%c", 39) }
        $0 !~ /^[[:space:]]*#/ && index($0, "=") > 0 {
            separator = index($0, "=")
            name = substr($0, 1, separator - 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
            if (name != wanted) next
            value = substr($0, separator + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            first = substr(value, 1, 1)
            last = substr(value, length(value), 1)
            if (length(value) >= 2 && ((first == "\"" && last == "\"") ||
                                      (first == single_quote && last == single_quote))) {
                value = substr(value, 2, length(value) - 2)
            }
            print value
            exit
        }
    ' "$CONF_FILE"
}

is_true() {
    case "${1,,}" in 1|true|yes|on) return 0 ;; *) return 1 ;; esac
}

fail() { printf 'CspoE installer: %s\n' "$*" >&2; exit 2; }

[[ -f "$CONF_FILE" ]] || fail "missing $CONF_FILE"
POOL_ID="$(conf_value BECH32_POOL_ID)"
POOL_TICKER="$(conf_value POOL_TICKER)"
POOL_FIRST_EPOCH="$(conf_value POOL_FIRST_EPOCH)"
BLOCKFROST_PROJECT_ID="$(conf_value BLOCKFROST_PROJECT_ID)"
INSTALL_ROOT="$(conf_value CSPOE_INSTALL_DIR)"; INSTALL_ROOT="${INSTALL_ROOT:-/opt/cspoe}"
SERVICE_USER="$(conf_value CSPOE_SERVICE_USER)"; SERVICE_USER="${SERVICE_USER:-cspoe}"
SERVICE_GROUP="$(conf_value CSPOE_SERVICE_GROUP)"; SERVICE_GROUP="${SERVICE_GROUP:-cspoe}"
WEB_DIR="$(conf_value CSPOE_WEB_DIR)"; WEB_DIR="${WEB_DIR:-/var/www/html/cspoe}"

[[ -n "$BLOCKFROST_PROJECT_ID" ]] || fail "set BLOCKFROST_PROJECT_ID in CspoE.conf"
[[ -n "$POOL_ID" ]] || fail "set BECH32_POOL_ID in CspoE.conf"
[[ -n "$POOL_TICKER" && "$POOL_TICKER" != "YOUR_POOL" ]] || fail "set POOL_TICKER in CspoE.conf"
[[ "$POOL_FIRST_EPOCH" =~ ^[1-9][0-9]*$ ]] || fail "POOL_FIRST_EPOCH must be the first active pool epoch"
[[ "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "invalid CSPOE_SERVICE_USER"
[[ "$SERVICE_GROUP" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "invalid CSPOE_SERVICE_GROUP"
[[ "$INSTALL_ROOT" = /* && "$INSTALL_ROOT" != "/" ]] || fail "CSPOE_INSTALL_DIR must be an absolute non-root path"
[[ "$WEB_DIR" = /* && "$WEB_DIR" != "/" ]] || fail "CSPOE_WEB_DIR must be an absolute non-root path"
[[ "$INSTALL_ROOT" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "CSPOE_INSTALL_DIR contains unsupported characters"
[[ "$WEB_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "CSPOE_WEB_DIR contains unsupported characters"

if [[ "$MODE" == "--check" ]]; then
    printf '{"ok":true,"mode":"check","pool_ticker":"%s","pool_first_epoch":%s,"install_dir":"%s"}\n' \
        "$POOL_TICKER" "$POOL_FIRST_EPOCH" "$INSTALL_ROOT"
    exit 0
fi
[[ "$MODE" == "--install" ]] || fail "usage: sudo ./install.sh [--check|--install]"
[[ "${EUID}" -eq 0 ]] || fail "--install must be run with sudo/root"

export DEBIAN_FRONTEND=noninteractive
apt-get update
packages=(python3 python3-venv python3-pip ca-certificates curl tar
          libgl1 libegl1 libfontconfig1 libdbus-1-3
          libxkbcommon0 libxkbcommon-x11-0
          libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0
          libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0
          libxcb-xfixes0)
if is_true "$(conf_value CSPOE_INSTALL_MYSQL)"; then
    packages+=(mysql-server)
fi
if is_true "$(conf_value CSPOE_INSTALL_PHP)"; then
    packages+=(apache2 php php-cli php-mysql)
fi
apt-get install -y "${packages[@]}"

getent group "$SERVICE_GROUP" >/dev/null || groupadd --system "$SERVICE_GROUP"
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --gid "$SERVICE_GROUP" --home-dir "$INSTALL_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
    usermod -a -G "$SERVICE_GROUP" "$SUDO_USER"
fi

if [[ "$SOURCE_ROOT" != "$INSTALL_ROOT" ]]; then
    if [[ -d "$INSTALL_ROOT" ]]; then
        [[ -z "$(find "$INSTALL_ROOT" -mindepth 1 -maxdepth 1 -print -quit)" ]] || \
            fail "target $INSTALL_ROOT is not empty; install into a new directory"
    fi
    mkdir -p "$INSTALL_ROOT"
    tar --exclude='.venv' --exclude='data/CspoE' --exclude='*.pyc' --exclude='__pycache__' \
        -C "$SOURCE_ROOT" -cf - . | tar -C "$INSTALL_ROOT" -xf -
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 2770 \
    "$INSTALL_ROOT/data/CspoE/epochs" "$INSTALL_ROOT/data/CspoE/live" \
    "$INSTALL_ROOT/data/CspoE/finalization_reports" "$INSTALL_ROOT/data/CspoE/replay_cache" \
    "$INSTALL_ROOT/data/CspoE/notifications" "$INSTALL_ROOT/data/CspoE/pooldata" \
    "$INSTALL_ROOT/data/CspoE/reconciliation_backups"
if [[ ! -f "$INSTALL_ROOT/data/awards.json" ]]; then
    printf '[]\n' > "$INSTALL_ROOT/data/awards.json"
fi
chown "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT/data/awards.json"
chmod 0660 "$INSTALL_ROOT/data/awards.json"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT"
chmod 0640 "$INSTALL_ROOT/CspoE.conf"

python3 -m venv "$INSTALL_ROOT/.venv"
"$INSTALL_ROOT/.venv/bin/python" -m pip install --upgrade pip wheel
"$INSTALL_ROOT/.venv/bin/pip" install -r "$INSTALL_ROOT/requirements-all.txt"
if is_true "$(conf_value CSPOE_TELEGRAM_INTERACTIVE_ENABLED)"; then
    "$INSTALL_ROOT/.venv/bin/pip" install -r "$INSTALL_ROOT/requirements-interactive.txt"
fi
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT/.venv"

if is_true "$(conf_value CSPOE_INSTALL_MYSQL)"; then
    MYSQL_DATABASE="$(conf_value MYSQL_DATABASE)"
    MYSQL_USER="$(conf_value MYSQL_USER)"
    MYSQL_PASSWORD="$(conf_value MYSQL_PASSWORD)"
    [[ "$MYSQL_DATABASE" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid MYSQL_DATABASE"
    [[ "$MYSQL_USER" =~ ^[A-Za-z0-9_]+$ ]] || fail "invalid MYSQL_USER"
    [[ -n "$MYSQL_PASSWORD" ]] || fail "MYSQL_PASSWORD is required when CSPOE_INSTALL_MYSQL=1"
    [[ "$MYSQL_PASSWORD" != *"'"* && "$MYSQL_PASSWORD" != *"\\"* ]] || \
        fail "MYSQL_PASSWORD must not contain quotes or backslashes for automated provisioning"
    MYSQL_PASSWORD_SQL="$MYSQL_PASSWORD"
    mysql --protocol=socket -uroot <<SQL
CREATE DATABASE IF NOT EXISTS \`$MYSQL_DATABASE\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$MYSQL_USER'@'localhost' IDENTIFIED BY '$MYSQL_PASSWORD_SQL';
ALTER USER '$MYSQL_USER'@'localhost' IDENTIFIED BY '$MYSQL_PASSWORD_SQL';
GRANT ALL PRIVILEGES ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'localhost';
FLUSH PRIVILEGES;
SQL
    mysql --protocol=socket -uroot "$MYSQL_DATABASE" < "$INSTALL_ROOT/sql/schema.sql"
    if is_true "$(conf_value CSPOE_MYSQL_LEGACY_COMPAT)"; then
        mysql --protocol=socket -uroot "$MYSQL_DATABASE" < "$INSTALL_ROOT/CspoE_legacy_schema.sql"
    fi
fi

if is_true "$(conf_value CSPOE_INSTALL_PHP)"; then
    install -d -o root -g www-data -m 0750 "$WEB_DIR" /etc/cspoe
    cp -a "$INSTALL_ROOT/php/." "$WEB_DIR/"
    chown -R root:www-data "$WEB_DIR"
    chmod -R u=rwX,g=rX,o= "$WEB_DIR"
    MYSQL_HOST="$(conf_value MYSQL_HOST)"; MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
    MYSQL_PORT="$(conf_value MYSQL_PORT)"; MYSQL_PORT="${MYSQL_PORT:-3306}"
    MYSQL_DATABASE="$(conf_value MYSQL_DATABASE)"
    MYSQL_USER="$(conf_value MYSQL_USER)"
    MYSQL_PASSWORD="$(conf_value MYSQL_PASSWORD)"
    php_escape() { printf '%s' "$1" | sed "s/'/\\\\'/g"; }
    cat > /etc/cspoe/php-db.php <<PHP
<?php
return [
  'MYSQL_HOST' => '$(php_escape "$MYSQL_HOST")',
  'MYSQL_PORT' => '$(php_escape "$MYSQL_PORT")',
  'MYSQL_DATABASE' => '$(php_escape "$MYSQL_DATABASE")',
  'MYSQL_USER' => '$(php_escape "$MYSQL_USER")',
  'MYSQL_PASSWORD' => '$(php_escape "$MYSQL_PASSWORD")',
];
PHP
    chown root:www-data /etc/cspoe/php-db.php
    chmod 0640 /etc/cspoe/php-db.php
    cat > /etc/apache2/conf-available/cspoe.conf <<APACHE
Alias /cspoe "$WEB_DIR"
SetEnv CSPOE_PHP_CONFIG /etc/cspoe/php-db.php
<Directory "$WEB_DIR">
    Options -Indexes
    AllowOverride None
    Require all granted
</Directory>
APACHE
    a2enconf cspoe
    systemctl reload apache2
fi

if is_true "$(conf_value CSPOE_ENABLE_SYSTEMD)"; then
    for template in "$INSTALL_ROOT"/systemd/*.service.in; do
        unit="$(basename "${template%.in}")"
        sed -e "s|@CSPOE_ROOT@|$INSTALL_ROOT|g" \
            -e "s|@CSPOE_USER@|$SERVICE_USER|g" \
            -e "s|@CSPOE_GROUP@|$SERVICE_GROUP|g" \
            "$template" > "/etc/systemd/system/$unit"
    done
    install -m 0644 "$INSTALL_ROOT"/systemd/*.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now cspoe-transition.timer
    if is_true "$(conf_value CSPOE_TELEGRAM_ENABLED)"; then systemctl enable --now cspoe-telegram.timer; fi
    if is_true "$(conf_value CSPOE_TELEGRAM_BLOCKS_ENABLED)"; then systemctl enable --now cspoe-block-watcher.timer; fi
    if is_true "$(conf_value CSPOE_TELEGRAM_STAKE_WATCHER_ENABLED)"; then systemctl enable --now cspoe-stake-watcher.timer; fi
    if is_true "$(conf_value CSPOE_TELEGRAM_DREP_ENABLED)"; then systemctl enable --now cspoe-drep-watcher.timer; fi
    if is_true "$(conf_value CSPOE_TELEGRAM_ADMIN_ENABLED)"; then systemctl enable --now cspoe-health.timer; fi
    if is_true "$(conf_value CSPOE_TELEGRAM_INTERACTIVE_ENABLED)"; then systemctl enable --now cspoe-telegram-interactive.service; fi
fi

runuser -u "$SERVICE_USER" -- "$INSTALL_ROOT/.venv/bin/python" "$INSTALL_ROOT/scripts/CspoE_initialization_selftest.py"
runuser -u "$SERVICE_USER" -- "$INSTALL_ROOT/.venv/bin/python" "$INSTALL_ROOT/scripts/CspoE_blockfrost_budget_selftest.py"
runuser -u "$SERVICE_USER" -- "$INSTALL_ROOT/.venv/bin/python" "$INSTALL_ROOT/scripts/CspoE_transaction_selftest.py"
printf '\nCspoE installed in %s. Run initialization explicitly as documented in INITIALIZE.md.\n' "$INSTALL_ROOT"
