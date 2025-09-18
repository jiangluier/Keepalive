#!/bin/bash

# 定义颜色
re="\033[0m"
red="\033[1;91m"
green="\e[1;32m"
yellow="\e[1;33m"
purple="\e[1;35m"
skyblue="\e[1;36m"
red() { echo -e "\e[1;91m$1\033[0m"; }
green() { echo -e "\e[1;32m$1\033[0m"; }
yellow() { echo -e "\e[1;33m$1\033[0m"; }
purple() { echo -e "\e[1;35m$1\033[0m"; }
skyblue() { echo -e "\e[1;36m$1\033[0m"; }
reading() { read -p "$(red "$1")" "$2"; }

# 定义常量
server_name="sing-box"
work_dir="/etc/sing-box"
config_dir="${work_dir}/config.json"
client_dir="${work_dir}/url.txt"

# 从外部环境变量获取端口，如果未提供则为空
export VL_PORT=${VL_PORT:-}
export SK_PORT=${SK_PORT:-}
export TU_PORT=${TU_PORT:-}
export HY_PORT=${HY_PORT:-}

# 内部固定端口和默认值
export vmess_argo_port=8001
export CFIP=${CFIP:-'cf.090227.xyz'}
export CFPORT=${CFPORT:-'8443'}

# 检查是否为root下运行
[[ $EUID -ne 0 ]] && red "请在root用户下运行脚本" && exit 1

# 检查 sing-box 是否已安装
check_singbox() {
if [ -f "${work_dir}/${server_name}" ]; then
    if [ -f /etc/alpine-release ]; then
        rc-service sing-box status | grep -q "started" && green "running" && return 0 || yellow "not running" && return 1
    else
        [ "$(systemctl is-active sing-box)" = "active" ] && green "running" && return 0 || yellow "not running" && return 1
    fi
else
    red "not installed"
    return 2
fi
}

# 检查 argo 是否已安装
check_argo() {
if [ -f "${work_dir}/argo" ]; then
    if [ -f /etc/alpine-release ]; then
        rc-service argo status | grep -q "started" && green "running" && return 0 || yellow "not running" && return 1
    else
        [ "$(systemctl is-active argo)" = "active" ] && green "running" && return 0 || yellow "not running" && return 1
    fi
else
    red "not installed"
    return 2
fi
}

#根据系统类型安装、卸载依赖
manage_packages() {
    if [ $# -lt 2 ]; then
        red "未指定的包名称或操作"
        return 1
    fi

    action=$1
    shift

    for package in "$@"; do
        if [ "$action" == "install" ]; then
            if command -v "$package" &>/dev/null; then
                green "${package} already installed"
                continue
            fi
            yellow "正在安装 ${package}..."
            if command -v apt &>/dev/null; then
                apt update && apt install -y "$package"
            elif command -v dnf &>/dev/null; then
                dnf install -y "$package"
            elif command -v yum &>/dev/null; then
                yum install -y "$package"
            elif command -v apk &>/dev/null; then
                apk update
                apk add "$package"
            else
                red "Unknown system!"
                return 1
            fi
        elif [ "$action" == "uninstall" ]; then
            if ! command -v "$package" >/dev/null; then
                yellow "${package} 没有安装"
                continue
            fi
            yellow "正在卸载 ${package}..."
            if command -v apt &>/dev/null; then
                apt remove -y "$package" && apt autoremove -y
            elif command -v dnf &>/dev/null; then
                dnf remove -y "$package" && dnf autoremove -y
            elif command -v yum &>/dev/null; then
                yum remove -y "$package" && yum autoremove -y
            elif command -v apk &>/dev/null; then
                apk del "$package"
            else
                red "未知系统！"
                return 1
            fi
        else
            red "未知操作: $action"
            return 1
        fi
    done
    return 0
}

# 获取 IP
get_realip() {
    ip=$(curl -s --max-time 2 ipv4.ip.sb)
    if [ -z "$ip" ]; then
        ipv6=$(curl -s --max-time 1 ipv6.ip.sb)
        echo "[$ipv6]"
    else
        if echo "$(curl -s http://ipinfo.io/org)" | grep -qE 'Cloudflare|UnReal|AEZA|Andrei'; then
            ipv6=$(curl -s --max-time 1 ipv6.ip.sb)
            echo "[$ipv6]"
        else
            echo "$ip"
        fi
    fi
}

# 下载并安装 sing-box,cloudflared
install_singbox() {
    clear
    purple "正在安装 sing-box 中，请稍后..."
    # 判断系统架构
    ARCH_RAW=$(uname -m)
    case "${ARCH_RAW}" in
        'x86_64') ARCH='amd64' ;;
        'x86' | 'i686' | 'i386') ARCH='386' ;;
        'aarch64' | 'arm64') ARCH='arm64' ;;
        'armv7l') ARCH='armv7' ;;
        's390x') ARCH='s390x' ;;
        *) red "不支持的架构: ${ARCH_RAW}"; exit 1 ;;
    esac
    # 下载 sing-box,cloudflared
    [ ! -d "${work_dir}" ] && mkdir -p "${work_dir}" && chmod 777 "${work_dir}"
    curl -sLo "${work_dir}/sing-box" "https://$ARCH.ssss.nyc.mn/sbx"
    curl -sLo "${work_dir}/argo" "https://$ARCH.ssss.nyc.mn/bot"
    chown root:root ${work_dir} && chmod +x ${work_dir}/${server_name} ${work_dir}/argo

    # 生成随机密码等
    socks_user="yutian"
    socks_pass="yutian=abcd"
    uuid=$(cat /proc/sys/kernel/random/uuid)
    password=$(< /dev/urandom tr -dc 'A-Za-z0-9' | head -c 24)
    output=$(/etc/sing-box/sing-box generate reality-keypair)
    private_key=$(echo "${output}" | awk '/PrivateKey:/ {print $2}')
    public_key=$(echo "${output}" | awk '/PublicKey:/ {print $2}')

    # IPv4 规则
    iptables -F > /dev/null 2>&1 \
      && iptables -P INPUT ACCEPT > /dev/null 2>&1 \
      && iptables -P FORWARD ACCEPT > /dev/null 2>&1 \
      && iptables -P OUTPUT ACCEPT > /dev/null 2>&1
    
    # IPv6 规则（先检查 ip6tables 是否存在）
    command -v ip6tables &> /dev/null \
      && ip6tables -F > /dev/null 2>&1 \
      && ip6tables -P INPUT ACCEPT > /dev/null 2>&1 \
      && ip6tables -P FORWARD ACCEPT > /dev/null 2>&1 \
      && ip6tables -P OUTPUT ACCEPT > /dev/null 2>&1
  
    manage_packages uninstall ufw firewalld > /dev/null 2>&1

    # 生成自签名证书
    openssl ecparam -genkey -name prime256v1 -out "${work_dir}/private.key"
    openssl req -new -x509 -days 3650 -key "${work_dir}/private.key" -out "${work_dir}/cert.pem" -subj "/CN=bing.com"

    # 初始化配置文件
    cat > "${config_dir}" << EOF
{
  "log": {
    "disabled": false,
    "level": "info",
    "output": "$work_dir/sb.log",
    "timestamp": true
  },
  "dns": {
    "servers": [
      {
        "tag": "google",
        "address": "tls://8.8.8.8"
      }
    ]
  },
  "inbounds": [],
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct"
    },
    {
      "type": "direct",
      "tag": "direct-ipv4-prefer-out",
      "domain_strategy": "prefer_ipv4"
    },
    {
      "type": "direct",
      "tag": "direct-ipv4-only-out",
      "domain_strategy": "ipv4_only"
    },
    {
      "type": "direct",
      "tag": "direct-ipv6-prefer-out",
      "domain_strategy": "prefer_ipv6"
    },
    {
      "type": "direct",
      "tag": "direct-ipv6-only-out",
      "domain_strategy": "ipv6_only"
    },
    {
      "type": "wireguard",
      "tag": "wireguard-out",
      "server": "engage.cloudflareclient.com",
      "server_port": 2408,
      "local_address": [
        "172.16.0.2/32",
        "2606:4700:110:812a:4929:7d2a:af62:351c/128"
      ],
      "private_key": "gBthRjevHDGyV0KvYwYE52NIPy29sSrVr6rcQtYNcXA=",
      "peer_public_key": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
      "reserved": [ 6, 146, 6 ]
    },
    {
      "type": "direct",
      "tag": "wireguard-ipv4-prefer-out",
      "detour": "wireguard-out",
      "domain_strategy": "prefer_ipv4"
    },
    {
      "type": "direct",
      "tag": "wireguard-ipv4-only-out",
      "detour": "wireguard-out",
      "domain_strategy": "ipv4_only"
    },
    {
      "type": "direct",
      "tag": "wireguard-ipv6-prefer-out",
      "detour": "wireguard-out",
      "domain_strategy": "prefer_ipv6"
    },
    {
      "type": "direct",
      "tag": "wireguard-ipv6-only-out",
      "detour": "wireguard-out",
      "domain_strategy": "ipv6_only"
    }
  ],
  "route": {
    "rule_set": [
      {
        "tag": "geosite-netflix",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/SagerNet/sing-geosite/rule-set/geosite-netflix.srs",
        "update_interval": "1d"
      },
      {
        "tag": "geosite-openai",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/sing/geo/geosite/openai.srs",
        "update_interval": "1d"
      }
    ],
    "rules": [
      {
        "rule_set": [ "geosite-netflix" ],
        "outbound": "wireguard-ipv6-only-out"
      },
      {
        "domain": [
          "api.statsig.com", "browser-intake-datadoghq.com", "cdn.openai.com", "chat.openai.com", "auth.openai.com",
          "chat.openai.com.cdn.cloudflare.net", "ios.chat.openai.com", "o33249.ingest.sentry.io",
          "openai-api.arkoselabs.com", "openaicom-api-bdcpf8c6d2e9atf6.z01.azurefd.net",
          "openaicomproductionae4b.blob.core.windows.net", "production-openaicom-storage.azureedge.net", "static.cloudflareinsights.com",
          "gemini.google.com","claude.ai","grok.com"
        ],
        "domain_suffix": [
          ".algolia.net", ".auth0.com", ".chatgpt.com", ".challenges.cloudflare.com", ".client-api.arkoselabs.com",
          ".events.statsigapi.net", ".featuregates.org", ".identrust.com", ".intercom.io", ".intercomcdn.com",
          ".launchdarkly.com", ".oaistatic.com", ".oaiusercontent.com", ".observeit.net", ".openai.com",
          ".openaiapi-site.azureedge.net", ".openaicom.imgix.net", ".segment.io", ".sentry.io", ".stripe.com"
        ],
        "domain_keyword": [ "openaicom-api" ],
        "outbound": "wireguard-ipv6-prefer-out"
      }
    ],
    "final": "direct"
   },
   "experimental": {
      "cache_file": { "enabled": true, "path": "$work_dir/cache.db", "cache_id": "mycacheid", "store_fakeip": true }
  }
}
EOF

    # -- 按需添加入站规则 --
    # VLESS Reality Inbound
    if [[ -n "$VL_PORT" ]]; then
        vless_inbound=$(cat <<EOF
{
    "tag": "vless-reality-in",
    "type": "vless",
    "listen": "::",
    "listen_port": $VL_PORT,
    "users": [ { "uuid": "$uuid", "flow": "xtls-rprx-vision" } ],
    "tls": {
        "enabled": true,
        "server_name": "www.iij.ad.jp",
        "reality": {
            "enabled": true,
            "handshake": { "server": "www.iij.ad.jp", "server_port": 443 },
            "private_key": "$private_key",
            "public_key": "$public_key",
            "short_id": [ "" ]
        }
    }
}
EOF
)
        jq ".inbounds += [$vless_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
    fi

    # VMess WS Inbound (Argo) - 总是添加
    vmess_inbound=$(cat <<EOF
{
    "tag": "vmess-ws-in",
    "type": "vmess",
    "listen": "::",
    "listen_port": $vmess_argo_port,
    "users": [ { "uuid": "$uuid" } ],
    "transport": { "type": "ws", "path": "/vmess-argo", "early_data_header_name": "Sec-WebSocket-Protocol" }
}
EOF
)
    jq ".inbounds += [$vmess_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"

    # SOCKS Inbound
    if [[ -n "$SK_PORT" ]]; then
        socks_inbound=$(cat <<EOF
{
    "tag": "socks-in",
    "type": "socks",
    "listen": "::",
    "listen_port": $SK_PORT,
    "users": [ { "username": "$socks_user", "password": "$socks_pass" } ]
}
EOF
)
        jq ".inbounds += [$socks_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
    fi

    # Hysteria2 Inbound
    if [[ -n "$HY_PORT" ]]; then
        hy2_inbound=$(cat <<EOF
{
    "tag": "hysteria2-in",
    "type": "hysteria2",
    "listen": "::",
    "listen_port": $HY_PORT,
    "sniff": true,
    "sniff_override_destination": false,
    "users": [ { "password": "$uuid" } ],
    "ignore_client_bandwidth": false,
    "masquerade": "https://bing.com",
    "tls": {
        "enabled": true, "alpn": [ "h3" ], "min_version": "1.3", "max_version": "1.3",
        "certificate_path": "$work_dir/cert.pem", "key_path": "$work_dir/private.key"
    }
}
EOF
)
        jq ".inbounds += [$hy2_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
    fi

    # TUIC Inbound
    if [[ -n "$TU_PORT" ]]; then
        tuic_inbound=$(cat <<EOF
{
    "tag": "tuic-in",
    "type": "tuic",
    "listen": "::",
    "listen_port": $TU_PORT,
    "users": [ { "uuid": "$uuid", "password": "$password" } ],
    "congestion_control": "bbr",
    "tls": {
        "enabled": true, "alpn": [ "h3" ],
        "certificate_path": "$work_dir/cert.pem", "key_path": "$work_dir/private.key"
   }
}
EOF
)
        jq ".inbounds += [$tuic_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
    fi
}

# debian/ubuntu/centos 守护进程
main_systemd_services() {
    cat > /etc/systemd/system/sing-box.service << EOF
[Unit]
Description=sing-box service
Documentation=https://sing-box.sagernet.org
After=network.target nss-lookup.target

[Service]
User=root
WorkingDirectory=/etc/sing-box
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
ExecStart=/etc/sing-box/sing-box run -c /etc/sing-box/config.json
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=10
LimitNOFILE=infinity

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/argo.service << EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
NoNewPrivileges=yes
TimeoutStartSec=0
ExecStart=/bin/sh -c "/etc/sing-box/argo tunnel --url http://localhost:$vmess_argo_port --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1"
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF
    if [ -f /etc/centos-release ]; then
        yum install -y chrony
        systemctl start chronyd
        systemctl enable chronyd
        chronyc -a makestep
        yum update -y ca-certificates
        bash -c 'echo "0 0" > /proc/sys/net/ipv4/ping_group_range'
    fi
    systemctl daemon-reload
    systemctl enable sing-box
    systemctl start sing-box
    systemctl enable argo
    systemctl start argo
}

# 适配alpine 守护进程
alpine_openrc_services() {
    cat > /etc/init.d/sing-box << 'EOF'
#!/sbin/openrc-run

description="sing-box service"
command="/etc/sing-box/sing-box"
command_args="run -c /etc/sing-box/config.json"
command_background=true
pidfile="/var/run/sing-box.pid"
EOF

    cat > /etc/init.d/argo << EOF
#!/sbin/openrc-run

description="Cloudflare Tunnel"
command="/bin/sh"
command_args="-c '/etc/sing-box/argo tunnel --url http://localhost:$vmess_argo_port --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1'"
command_background=true
pidfile="/var/run/argo.pid"
EOF

    chmod +x /etc/init.d/sing-box
    chmod +x /etc/init.d/argo
    rc-update add sing-box default
    rc-update add argo default
}

get_info() {
    clear
    # 从配置文件中读取最新信息
    uuid=$(jq -r '.inbounds[] | select(.users[].uuid) | .users[].uuid' "$config_dir" | head -n1)
    password=$(jq -r '.inbounds[] | select(.type == "tuic") | .users[].password' "$config_dir" | head -n1)
    public_key=$(jq -r '.inbounds[] | select(.type == "vless") | .tls.reality.public_key' "$config_dir" | head -n1)
    socks_user=$(jq -r '.inbounds[] | select(.type == "socks") | .users[].username' "$config_dir" | head -n1)
    socks_pass=$(jq -r '.inbounds[] | select(.type == "socks") | .users[].password' "$config_dir" | head -n1)
    
    VL_PORT=$(jq -r '.inbounds[] | select(.type == "vless") | .listen_port' "$config_dir" | head -n1)
    SK_PORT=$(jq -r '.inbounds[] | select(.type == "socks") | .listen_port' "$config_dir" | head -n1)
    HY_PORT=$(jq -r '.inbounds[] | select(.type == "hysteria2") | .listen_port' "$config_dir" | head -n1)
    TU_PORT=$(jq -r '.inbounds[] | select(.type == "tuic") | .listen_port' "$config_dir" | head -n1)

    server_ip=$(get_realip)
    isp=$(curl -s --max-time 2 https://speed.cloudflare.com/meta | awk -F\" '{print $26"-"$18}' | sed -e 's/ /_/g' || echo "vps")

    # 获取Argo域名
    if [ -f "${work_dir}/argo.log" ]; then
        for i in {1..5}; do
            purple "第 $i 次尝试获取ArgoDomain中..."
            argodomain=$(sed -n 's|.*https://\([^/]*trycloudflare\.com\).*|\1|p' "${work_dir}/argo.log")
            [ -n "$argodomain" ] && break
            sleep 2
        done
    else
        restart_argo
        sleep 6
        argodomain=$(sed -n 's|.*https://\([^/]*trycloudflare\.com\).*|\1|p' "${work_dir}/argo.log")
    fi
    [ -z "$argodomain" ] && red "获取Argo域名失败，请检查Argo服务日志！"

    green "\nArgoDomain: ${purple}$argodomain${re}\n"
    
    # 清空旧文件并按需生成分享链接
    > "${work_dir}/url.txt"

    # VLESS
    if [[ -n "$VL_PORT" && "$VL_PORT" != "null" ]]; then
        echo "vless://${uuid}@${server_ip}:${VL_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${public_key}&type=tcp&headerType=none#${isp}_VLESS" >> ${work_dir}/url.txt
    fi

    # VMess (Argo) - 总是生成
    VMESS="{ \"v\": \"2\", \"ps\": \"${isp}_VMESS_ARGO\", \"add\": \"${CFIP}\", \"port\": \"${CFPORT}\", \"id\": \"${uuid}\", \"aid\": \"0\", \"scy\": \"none\", \"net\": \"ws\", \"type\": \"none\", \"host\": \"${argodomain}\", \"path\": \"/vmess-argo?ed=2048\", \"tls\": \"tls\", \"sni\": \"${argodomain}\", \"alpn\": \"\", \"fp\": \"randomized\"}"
    echo "vmess://$(echo "$VMESS" | base64 -w0)" >> ${work_dir}/url.txt

    # Hysteria2
    if [[ -n "$HY_PORT" && "$HY_PORT" != "null" ]]; then
        echo "hysteria2://${uuid}@${server_ip}:${HY_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${isp}_HY2" >> ${work_dir}/url.txt
    fi

    # TUIC
    if [[ -n "$TU_PORT" && "$TU_PORT" != "null" ]]; then
        echo "tuic://${uuid}:${password}@${server_ip}:${TU_PORT}?sni=www.bing.com&congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#${isp}_TUIC" >> ${work_dir}/url.txt
    fi

    # SOCKS
    if [[ -n "$SK_PORT" && "$SK_PORT" != "null" ]]; then
        echo "socks5://$socks_user:$socks_pass@${server_ip}:$SK_PORT#${isp}_SOCKS" >> ${work_dir}/url.txt
    fi

    echo ""
    while IFS= read -r line; do echo -e "${purple}$line"; done < ${work_dir}/url.txt
    yellow "\n温馨提醒：Hysteria2/TUIC节点需打开客户端里的 “跳过证书验证”，或将节点的Insecure/allow_insecure设置为“true”\n"
    echo ""
}

# 启动 sing-box
start_singbox() {
    check_singbox &>/dev/null; local status=$?
    if [ $status -eq 1 ]; then
        yellow "正在启动 ${server_name} 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service sing-box start
        else
            systemctl daemon-reload
            systemctl start "${server_name}"
        fi
        if [ $? -eq 0 ]; then
            green "${server_name} 服务已成功启动\n"
        else
            red "${server_name} 服务启动失败\n"
        fi
    elif [ $status -eq 0 ]; then
        yellow "sing-box 正在运行\n"
    else
        yellow "sing-box 尚未安装!\n"
    fi
    sleep 1
}

# 停止 sing-box
stop_singbox() {
    check_singbox &>/dev/null; local status=$?
    if [ $status -eq 0 ]; then
        yellow "正在停止 ${server_name} 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service sing-box stop
        else
            systemctl stop "${server_name}"
        fi
        if [ $? -eq 0 ]; then
            green "${server_name} 服务已成功停止\n"
        else
            red "${server_name} 服务停止失败\n"
        fi
    elif [ $status -eq 1 ]; then
        yellow "sing-box 未运行\n"
    else
        yellow "sing-box 尚未安装！\n"
    fi
    sleep 1
}

# 重启 sing-box
restart_singbox() {
    check_singbox &>/dev/null; local status=$?
    if [ $status -eq 0 ] || [ $status -eq 1 ]; then
        yellow "正在重启 ${server_name} 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service ${server_name} restart
        else
            systemctl daemon-reload
            systemctl restart "${server_name}"
        fi
        if [ $? -eq 0 ]; then
            green "${server_name} 服务已成功重启\n"
        else
            red "${server_name} 服务重启失败\n"
        fi
    else
        yellow "sing-box 尚未安装！\n"
    fi
    sleep 1
}

# 启动 argo
start_argo() {
    check_argo &>/dev/null; local status=$?
    if [ $status -eq 1 ]; then
        yellow "正在启动 Argo 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service argo start
        else
            systemctl daemon-reload
            systemctl start argo
        fi
        if [ $? -eq 0 ]; then
            green "Argo 服务已成功启动\n"
        else
            red "Argo 服务启动失败\n"
        fi
    elif [ $status -eq 0 ]; then
        green "Argo 服务正在运行\n"
    else
        yellow "Argo 尚未安装！\n"
    fi
    sleep 1
}

# 停止 argo
stop_argo() {
    check_argo &>/dev/null; local status=$?
    if [ $status -eq 0 ]; then
        yellow "正在停止 Argo 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service argo stop
        else
            systemctl stop argo
        fi
        if [ $? -eq 0 ]; then
            green "Argo 服务已成功停止\n"
        else
            red "Argo 服务停止失败\n"
        fi
    elif [ $status -eq 1 ]; then
        yellow "Argo 服务未运行\n"
    else
        yellow "Argo 尚未安装！\n"
    fi
    sleep 1
}

# 重启 argo
restart_argo() {
    check_argo &>/dev/null; local status=$?
    if [ $status -eq 0 ] || [ $status -eq 1 ]; then
        yellow "正在重启 Argo 服务\n"
        if [ -f /etc/alpine-release ]; then
            rc-service argo restart
        else
            systemctl daemon-reload
            systemctl restart argo
        fi
        if [ $? -eq 0 ]; then
            green "Argo 服务已成功重启\n"
        else
            red "Argo 服务重启失败\n"
        fi
    else
        yellow "Argo 尚未安装！\n"
    fi
    sleep 1
}

# 卸载 sing-box
uninstall_singbox() {
   reading "确定要卸载 sing-box 吗? (y/n): " choice
   case "${choice}" in
       y|Y)
           yellow "正在卸载 sing-box"
           if [ -f /etc/alpine-release ]; then
                rc-service sing-box stop
                rc-service argo stop
                rm /etc/init.d/sing-box /etc/init.d/argo
                rc-update del sing-box default
                rc-update del argo default
           else
                systemctl stop "${server_name}"
                systemctl stop argo
                systemctl disable "${server_name}"
                systemctl disable argo
                rm -f /etc/systemd/system/sing-box.service /etc/systemd/system/argo.service
                systemctl daemon-reload || true
            fi
           rm -rf "${work_dir}"
           rm -f /usr/bin/sb
           green "\nsing-box 卸载成功\n\n" && exit 0
           ;;
       *)
           purple "已取消卸载操作\n\n"
           ;;
   esac
}

# 创建快捷指令
create_shortcut() {
    cat > "$work_dir/sb.sh" << EOF
#!/usr/bin/env bash
bash <(curl -Ls https://raw.githubusercontent.com/yutian81/Keepalive/main/vps_sb5in1.sh) \$1
EOF
    chmod +x "$work_dir/sb.sh"
    ln -sf "$work_dir/sb.sh" /usr/bin/sb
    if [ -s /usr/bin/sb ]; then
        green "\n快捷指令 sb 创建成功\n"
    else
        red "\n快捷指令创建失败\n"
    fi
}

# 适配alpine运行argo报错用户组和dns的问题
change_hosts() {
    sh -c 'echo "0 0" > /proc/sys/net/ipv4/ping_group_range'
    sed -i '1s/.*/127.0.0.1   localhost/' /etc/hosts
    sed -i '2s/.*/::1         localhost/' /etc/hosts
}

# 变更配置
change_config() {
    check_singbox &>/dev/null
    if [ $? -eq 2 ]; then
        yellow "sing-box 尚未安装！"
        sleep 1
        return
    fi

    # 检测节点是否存在
    has_vless=$(jq -e '.inbounds[] | select(.type == "vless")' "$config_dir" >/dev/null && echo "true" || echo "false")
    has_socks=$(jq -e '.inbounds[] | select(.type == "socks")' "$config_dir" >/dev/null && echo "true" || echo "false")
    has_hy2=$(jq -e '.inbounds[] | select(.type == "hysteria2")' "$config_dir" >/dev/null && echo "true" || echo "false")
    has_tuic=$(jq -e '.inbounds[] | select(.type == "tuic")' "$config_dir" >/dev/null && echo "true" || echo "false")

    clear
    echo ""
    if [[ "$has_vless" == "true" ]]; then green "1. 修改 VLESS-Reality 端口"; else yellow "1. 添加 VLESS-Reality 节点"; fi
    skyblue "------------"
    if [[ "$has_socks" == "true" ]]; then green "2. 修改 SOCKS5 端口"; else yellow "2. 添加 SOCKS5 节点"; fi
    skyblue "------------"
    if [[ "$has_hy2" == "true" ]]; then green "3. 修改 Hysteria2 端口"; else yellow "3. 添加 Hysteria2 节点"; fi
    skyblue "------------"
    if [[ "$has_tuic" == "true" ]]; then green "4. 修改 TUIC 端口"; else yellow "4. 添加 TUIC 节点"; fi
    skyblue "------------"
    green "5. 修改通用 UUID"
    skyblue "------------"
    green "6. 修改 Reality 伪装域名"
    skyblue "------------"
    green "7. 添加 Hysteria2 端口跳跃"
    skyblue "------------"
    green "8. 删除 Hysteria2 端口跳跃"
    skyblue "------------"
    purple "9. 返回主菜单"
    skyblue "------------"
    reading "请输入选择: " choice

    case "${choice}" in
        1|2|3|4)
            local protocol type tag listen_port
            case "$choice" in
                1) protocol="VLESS"; type="vless"; tag="vless-reality-in";;
                2) protocol="SOCKS5"; type="socks"; tag="socks-in";;
                3) protocol="Hysteria2"; type="hysteria2"; tag="hysteria2-in";;
                4) protocol="TUIC"; type="tuic"; tag="tuic-in";;
            esac

            # 检查节点是否存在
            if ! jq -e --arg t "$type" '.inbounds[] | select(.type == $t)' "$config_dir" >/dev/null; then
                # 添加节点
                reading "\n请输入新的 ${protocol} 端口 (回车跳过将使用随机端口): " new_port
                [ -z "$new_port" ] && new_port=$(shuf -i 10000-65000 -n 1)
                
                # 重新生成一份该节点的配置并插入
                # 为了简化，这里直接调用初次安装的逻辑，需要准备好所有变量
                uuid=$(jq -r '.inbounds[0].users[0].uuid' "$config_dir")
                password=$(< /dev/urandom tr -dc 'A-Za-z0-9' | head -c 24)
                private_key=$(jq -r '.inbounds[] | select(.type == "vless") | .tls.reality.private_key // ""' "$config_dir" | head -n1)
                if [[ -z "$private_key" && "$type" == "vless" ]]; then
                    output=$(/etc/sing-box/sing-box generate reality-keypair)
                    private_key=$(echo "${output}" | awk '/PrivateKey:/ {print $2}')
                    public_key=$(echo "${output}" | awk '/PublicKey:/ {print $2}')
                fi
                socks_user="yutian"; socks_pass="yutian=abcd"
                work_dir="/etc/sing-box"

                local new_inbound
                case "$type" in
                    "vless") new_inbound=$(cat <<EOF
{"tag":"$tag","type":"vless","listen":"::","listen_port":$new_port,"users":[{"uuid":"$uuid","flow":"xtls-rprx-vision"}],"tls":{"enabled":true,"server_name":"www.iij.ad.jp","reality":{"enabled":true,"handshake":{"server":"www.iij.ad.jp","server_port":443},"private_key":"$private_key","public_key":"$public_key","short_id":[""]}}}
EOF
) ;;
                    "socks") new_inbound=$(cat <<EOF
{"tag":"$tag","type":"socks","listen":"::","listen_port":$new_port,"users":[{"username":"$socks_user","password":"$socks_pass"}]}
EOF
) ;;
                    "hysteria2") new_inbound=$(cat <<EOF
{"tag":"$tag","type":"hysteria2","listen":"::","listen_port":$new_port,"sniff":true,"sniff_override_destination":false,"users":[{"password":"$uuid"}],"ignore_client_bandwidth":false,"masquerade":"https://bing.com","tls":{"enabled":true,"alpn":["h3"],"min_version":"1.3","max_version":"1.3","certificate_path":"$work_dir/cert.pem","key_path":"$work_dir/private.key"}}
EOF
) ;;
                    "tuic") new_inbound=$(cat <<EOF
{"tag":"$tag","type":"tuic","listen":"::","listen_port":$new_port,"users":[{"uuid":"$uuid","password":"$password"}],"congestion_control":"bbr","tls":{"enabled":true,"alpn":["h3"],"certificate_path":"$work_dir/cert.pem","key_path":"$work_dir/private.key"}}
EOF
) ;;
                esac
                jq ".inbounds += [$new_inbound]" "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
                green "\n${protocol} 节点已添加，端口为：${purple}${new_port}${re}\n"
            else
                # 修改端口
                reading "\n请输入新的 ${protocol} 端口 (回车跳过将使用随机端口): " new_port
                [ -z "$new_port" ] && new_port=$(shuf -i 10000-65000 -n 1)
                jq --arg t "$type" --argjson p "$new_port" '(.inbounds[] | select(.type == $t) | .listen_port) = $p' "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
                green "\n${protocol} 端口已修改为：${purple}${new_port}${re}\n"
            fi
            restart_singbox
            get_info
            ;;
        5)
            reading "\n请输入新的UUID (回车留空将自动生成): " new_uuid
            [ -z "$new_uuid" ] && new_uuid=$(cat /proc/sys/kernel/random/uuid)
            
            # 使用jq更新所有inbound中的uuid和password(hysteria2)
            jq --arg u "$new_uuid" '
                .inbounds = [
                    .inbounds[] | 
                    if .users then .users = [
                        .users[] | 
                        if .uuid then .uuid = $u else . end |
                        if .password and (.password | length > 20) then .password = $u else . end
                    ] else . end
                ]' "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"

            restart_singbox
            get_info
            green "\n通用UUID已修改为：${purple}${new_uuid}${re}\n"
            ;;
        6) 
            clear
            green "\n1. www.joom.com\n2. www.stengg.com\n3. www.wedgehr.com\n4. www.cerebrium.ai\n5. www.nazhumi.com\n"
            reading "请输入新的Reality伪装域名(可自定义输入,回车将使用默认1): " new_sni
            case "$new_sni" in
                "") new_sni="www.joom.com" ;;
                "1") new_sni="www.joom.com" ;;
                "2") new_sni="www.stengg.com" ;;
                "3") new_sni="www.wedgehr.com" ;;
                "4") new_sni="www.cerebrium.ai" ;;
                "5") new_sni="www.nazhumi.com" ;;
            esac
            jq --arg new_sni "$new_sni" '
                (.inbounds[] | select(.type == "vless") | .tls.server_name) = $new_sni |
                (.inbounds[] | select(.type == "vless") | .tls.reality.handshake.server) = $new_sni
                ' "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
            restart_singbox
            get_info
            green "\nReality SNI已修改为：${purple}${new_sni}${re}\n"
            ;;
        7) 
            if ! jq -e '.inbounds[] | select(.type == "hysteria2")' "$config_dir" >/dev/null; then
                red "Hysteria2 节点不存在，无法添加端口跳跃！"
                sleep 2
                return
            fi
            purple "端口跳跃需确保跳跃区间的端口没有被占用，nat鸡请注意可用端口范围，否则可能造成节点不通\n"
            reading "请输入跳跃起始端口 (回车跳过将使用随机端口): " min_port
            [ -z "$min_port" ] && min_port=$(shuf -i 50000-65000 -n 1)
            yellow "你的起始端口为：$min_port"
            reading "\n请输入跳跃结束端口 (需大于起始端口): " max_port
            [ -z "$max_port" ] && max_port=$(($min_port + 100)) 
            yellow "你的结束端口为：$max_port\n"
            purple "正在安装依赖，并设置端口跳跃规则中，请稍等...\n"
            listen_port=$(jq -r '.inbounds[] | select(.type == "hysteria2") | .listen_port' "$config_dir")
            iptables -t nat -A PREROUTING -p udp --dport $min_port:$max_port -j DNAT --to-destination :$listen_port > /dev/null
            command -v ip6tables &> /dev/null && ip6tables -t nat -A PREROUTING -p udp --dport $min_port:$max_port -j DNAT --to-destination :$listen_port > /dev/null
            # 持久化规则
            if command -v iptables-save >/dev/null; then
                if [ -f /etc/alpine-release ]; then
                    mkdir -p /etc/iptables
                    iptables-save > /etc/iptables/rules.v4
                    command -v ip6tables &> /dev/null && ip6tables-save > /etc/iptables/rules.v6
                    cat > /etc/init.d/iptables-rules << 'EOF'
#!/sbin/openrc-run
description="Restore iptables rules"
start() {
    [ -f /etc/iptables/rules.v4 ] && iptables-restore < /etc/iptables/rules.v4
    command -v ip6tables &> /dev/null && [ -f /etc/iptables/rules.v6 ] && ip6tables-restore < /etc/iptables/rules.v6
}
EOF
                    chmod +x /etc/init.d/iptables-rules && rc-update add iptables-rules default
                elif command -v netfilter-persistent >/dev/null; then
                    netfilter-persistent save
                elif command -v service >/dev/null && [ -f /etc/init.d/iptables ]; then
                    service iptables save
                    command -v ip6tables &> /dev/null && service ip6tables save
                fi
            fi
            green "\nhysteria2端口跳跃已开启,跳跃端口为：${purple}$min_port-$max_port${re}\n"
            ;;
        8) 
            iptables -t nat -F PREROUTING  > /dev/null 2>&1
            command -v ip6tables &> /dev/null && ip6tables -t nat -F PREROUTING  > /dev/null 2>&1
            # 持久化清空后的规则
             if command -v iptables-save >/dev/null; then
                if [ -f /etc/alpine-release ]; then
                    rm -f /etc/init.d/iptables-rules && rc-update del iptables-rules default
                elif command -v netfilter-persistent >/dev/null; then
                    netfilter-persistent save
                elif command -v service >/dev/null && [ -f /etc/init.d/iptables ]; then
                    service iptables save
                    command -v ip6tables &> /dev/null && service ip6tables save
                fi
            fi
            green "\n端口跳跃已删除\n"
            ;;
        9)  return ;;
        *)  red "无效的选项！" ;;
    esac
}

# singbox 管理
manage_singbox() {
    clear
    echo ""
    green "1. 启动sing-box服务"
    skyblue "-------------------"
    green "2. 停止sing-box服务"
    skyblue "-------------------"
    green "3. 重启sing-box服务"
    skyblue "-------------------"
    purple "4. 返回主菜单"
    skyblue "------------"
    reading "\n请输入选择: " choice
    case "${choice}" in
        1) start_singbox ;;
        2) stop_singbox ;;
        3) restart_singbox ;;
        4) return ;;
        *) red "无效的选项！" ;;
    esac
}

# Argo 管理
manage_argo() {
    check_argo &>/dev/null
    if [ $? -eq 2 ]; then
        yellow "Argo 尚未安装！"
        sleep 1
        return
    fi
    clear
    echo ""
    green "1. 启动Argo服务"
    skyblue "------------"
    green "2. 停止Argo服务"
    skyblue "------------"
    green "3. 重启Argo服务"
    skyblue "------------"
    green "4. 添加Argo固定隧道"
    skyblue "----------------"
    green "5. 切换回Argo临时隧道"
    skyblue "------------------"
    green "6. 重新获取Argo临时域名"
    skyblue "-------------------"
    purple "7. 返回主菜单"
    skyblue "-----------"
    reading "\n请输入选择: " choice
    case "${choice}" in
        1)  start_argo ;;
        2)  stop_argo ;;
        3)  restart_argo ;;
        4)
            clear
            yellow "\n固定隧道可为json或token，固定隧道端口为${vmess_argo_port}，自行在cf后台设置\n\njson在f佬维护的站点里获取，获取地址：${purple}https://fscarmen.cloudflare.now.cc${re}\n"
            reading "\n请输入你的argo域名: " argo_domain
            ArgoDomain=$argo_domain
            reading "\n请输入你的argo密钥(token或json): " argo_auth
            if [[ $argo_auth =~ TunnelSecret ]]; then
                echo "$argo_auth" > ${work_dir}/tunnel.json
                tunnel_id=$(jq -r .TunnelID <<< "$argo_auth")
                cat > ${work_dir}/tunnel.yml << EOF
tunnel: $tunnel_id
credentials-file: ${work_dir}/tunnel.json
protocol: http2

ingress:
  - hostname: $ArgoDomain
    service: http://localhost:$vmess_argo_port
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
                if [ -f /etc/alpine-release ]; then
                    sed -i "/^command_args=/c\command_args=\"-c '/etc/sing-box/argo tunnel --edge-ip-version auto --config /etc/sing-box/tunnel.yml run'\"" /etc/init.d/argo
                else
                    sed -i '/^ExecStart=/c ExecStart=/bin/sh -c "/etc/sing-box/argo tunnel --edge-ip-version auto --config /etc/sing-box/tunnel.yml run"' /etc/systemd/system/argo.service
                fi
                restart_argo
                change_argo_domain
            elif [[ $argo_auth =~ ^[A-Z0-9a-z=]{120,250}$ ]]; then
                if [ -f /etc/alpine-release ]; then
                    sed -i "/^command_args=/c\command_args=\"-c '/etc/sing-box/argo tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token $argo_auth'\"" /etc/init.d/argo
                else
                    sed -i "/^ExecStart=/c ExecStart=/bin/sh -c \"/etc/sing-box/argo tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token '$argo_auth'\"" /etc/systemd/system/argo.service
                fi
                restart_argo
                change_argo_domain
            else
                red "你输入的argo域名或token不匹配，请重新输入"
                sleep 2
            fi
            ;;
        5)
            clear
            if [ -f /etc/alpine-release ]; then
                sed -i "/^command_args=/c\command_args=\"-c '/etc/sing-box/argo tunnel --url http://localhost:$vmess_argo_port --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1'\"" /etc/init.d/argo
            else
                sed -i "/^ExecStart=/c ExecStart=/bin/sh -c \"/etc/sing-box/argo tunnel --url http://localhost:$vmess_argo_port --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1\"" /etc/systemd/system/argo.service
            fi
            get_quick_tunnel
            change_argo_domain
            ;;
        6) 
            get_quick_tunnel
            change_argo_domain
            ;;
        7)  return ;;
        *)  red "无效的选项！" ;;
    esac
}

# 获取argo临时隧道
get_quick_tunnel() {
    restart_argo
    yellow "获取临时argo域名中，请稍等...\n"
    for i in {1..5}; do
        purple "第 $i 次尝试获取ArgoDomain中..."
        ArgoDomain=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "${work_dir}/argo.log" | sed 's/https:\/\///')
        [ -n "$ArgoDomain" ] && break
        sleep 2
    done
    if [ -z "$ArgoDomain" ]; then
        red "获取临时隧道失败！请检查argo日志。"
    else
        green "ArgoDomain：${purple}$ArgoDomain${re}\n"
    fi
}

# 更新Argo域名到节点链接
change_argo_domain() {
    if [ -z "$ArgoDomain" ] || [ ! -f "$client_dir" ]; then
        red "Argo域名为空或链接文件不存在，无法更新。"
        return
    fi
    # 使用jq安全地更新vmess链接中的host和sni
    vmess_line=$(grep 'vmess://' "$client_dir")
    if [ -n "$vmess_line" ]; then
        encoded_part=$(echo "$vmess_line" | sed 's/vmess:\/\///')
        decoded_json=$(echo "$encoded_part" | base64 -d)
        updated_json=$(echo "$decoded_json" | jq --arg domain "$ArgoDomain" '.host = $domain | .sni = $domain')
        new_encoded_part=$(echo "$updated_json" | base64 -w0)
        sed -i "s|$encoded_part|$new_encoded_part|" "$client_dir"
        green "vmess节点已更新,请手动复制最新的vmess-argo节点\n"
        purple "vmess://$new_encoded_part\n"
    fi
}

# 查看节点信息
check_nodes() {
    check_singbox &>/dev/null
    if [ $? -eq 2 ]; then
        yellow "sing-box 尚未安装或未运行,请先安装或启动sing-box"
    else
        while IFS= read -r line; do purple "$line"; done < ${work_dir}/url.txt
    fi
    sleep 1
}

# 主菜单
menu() {
   check_singbox &>/dev/null; check_singbox=$?
   check_argo &>/dev/null; check_argo=$?

   check_singbox_status=$(check_singbox)
   check_argo_status=$(check_argo)
   clear
   echo ""
   purple "=== 老王sing-box一键安装脚本 (定制版) ===\n"
   purple "---Argo--- 状态: ${check_argo_status}"
   purple "---singbox--- 状态: ${check_singbox_status}\n"
   green "1. 安装sing-box"
   red "2. 卸载sing-box"
   echo "==============="
   green "3. sing-box管理"
   green "4. Argo隧道管理"
   echo  "==============="
   green  "5. 查看节点信息"
   green  "6. 修改节点配置"
   echo  "==============="
   purple "7. SSH综合工具箱"
   echo  "==============="
   red "0. 退出脚本"
   echo "==========="
   reading "请输入选择(0-7): " choice
   echo ""
}

# 捕获 Ctrl+C 信号
trap 'echo -e "\n${red}已取消操作${re}"; exit 1' INT

# 主循环
while true; do
   menu
   case "${choice}" in
        1) 
            if [ $check_singbox -ne 2 ]; then
                yellow "sing-box 已经安装！"
            else
                if [[ -z "$VL_PORT" && -z "$SK_PORT" && -z "$TU_PORT" && -z "$HY_PORT" ]]; then
                    red "错误：至少需要通过环境变量指定一个端口才能进行安装！"
                    yellow "例如: VL_PORT=20001 bash <(curl ...)"
                    sleep 3
                    continue
                fi
                manage_packages install jq tar curl openssl iptables
                [ -n "$(curl -s --max-time 2 ipv6.ip.sb)" ] && manage_packages install ip6tables
                install_singbox

                if [ -x "$(command -v systemctl)" ]; then
                    main_systemd_services
                elif [ -x "$(command -v rc-update)" ]; then
                    alpine_openrc_services
                    change_hosts
                    rc-service sing-box restart
                    rc-service argo restart
                else
                    red "不支持的初始化系统"
                    exit 1
                fi

                sleep 5
                get_info
                create_shortcut
            fi
           ;;
        2) uninstall_singbox ;;
        3) manage_singbox ;;
        4) manage_argo ;;
        5) check_nodes ;;
        6) change_config ;;
        7) 
           clear
           curl -fsSLO ssh_tool.eooce.com && bash ssh_tool.sh
           ;;
        0) exit 0 ;;
        *) red "无效的选项，请输入 0 到 7" ;;
   esac
   read -n 1 -s -r -p $'\n\033[1;91m按任意键继续...\033[0m'
done
