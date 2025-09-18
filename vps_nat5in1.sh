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
pub_key_file="${work_dir}/reality.pub"

# 导入外部变量
# 示例: export VL_PORT=49752 bash <(curl ...)
export UUID=${UUID:-}
export VL_PORT=${VL_PORT:-}
export SK_PORT=${SK_PORT:-}
export TU_PORT=${TU_PORT:-}
export HY_PORT=${HY_PORT:-}
export ARGO_DOMAIN=${ARGO_DOMAIN:-}
export ARGO_AUTH=${ARGO_AUTH:-}
export ARGO_PORT=8001
export CFIP=${CFIP:-'cf.090227.xyz'}
export CFPORT=${CFPORT:-'8443'}
export IN_PORT=${IN_PORT:-34766}

# 检查是否为root下运行
[[ $EUID -ne 0 ]] && red "请在root用户下运行脚本" && exit 1

# 检查命令是否存在函数
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

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
                green "依赖 ${package} 已安装"
                continue
            fi
            yellow "正在安装依赖 ${package}..."
            if command -v apt-get &>/dev/null; then
                apt-get update && apt-get install -y "$package"
            elif command -v dnf &>/dev/null; then
                dnf install -y "$package"
            elif command -v yum &>/dev/null; then
                yum install -y "$package"
            elif command -v apk &>/dev/null; then
                apk update && apk add "$package"
            else
                red "无法识别的操作系统！"
                return 1
            fi
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

allow_port() {
    has_ufw=0
    has_firewalld=0
    has_iptables=0
    has_ip6tables=0

    command_exists ufw && has_ufw=1
    command_exists firewall-cmd && systemctl is-active firewalld >/dev/null 2>&1 && has_firewalld=1
    command_exists iptables && has_iptables=1
    command_exists ip6tables && has_ip6tables=1

    # 出站和基础规则
    [ "$has_ufw" -eq 1 ] && ufw --force default allow outgoing >/dev/null 2>&1
    [ "$has_firewalld" -eq 1 ] && firewall-cmd --permanent --zone=public --set-target=ACCEPT >/dev/null 2>&1
    [ "$has_iptables" -eq 1 ] && {
        iptables -C INPUT -i lo -j ACCEPT 2>/dev/null || iptables -I INPUT 3 -i lo -j ACCEPT
        iptables -C INPUT -p icmp -j ACCEPT 2>/dev/null || iptables -I INPUT 4 -p icmp -j ACCEPT
        iptables -P FORWARD DROP 2>/dev/null || true
        iptables -P OUTPUT ACCEPT 2>/dev/null || true
    }
    [ "$has_ip6tables" -eq 1 ] && {
        ip6tables -C INPUT -i lo -j ACCEPT 2>/dev/null || ip6tables -I INPUT 3 -i lo -j ACCEPT
        ip6tables -C INPUT -p icmp -j ACCEPT 2>/dev/null || ip6tables -I INPUT 4 -p icmp -j ACCEPT
        ip6tables -P FORWARD DROP 2>/dev/null || true
        ip6tables -P OUTPUT ACCEPT 2>/dev/null || true
    }

    # 入站
    for rule in "$@"; do
        port=${rule%/*}
        proto=${rule#*/}
        [ "$has_ufw" -eq 1 ] && ufw allow in ${port}/${proto} >/dev/null 2>&1
        [ "$has_firewalld" -eq 1 ] && firewall-cmd --permanent --add-port=${port}/${proto} >/dev/null 2>&1
        [ "$has_iptables" -eq 1 ] && (iptables -C INPUT -p ${proto} --dport ${port} -j ACCEPT 2>/dev/null || iptables -I INPUT 4 -p ${proto} --dport ${port} -j ACCEPT)
        [ "$has_ip6tables" -eq 1 ] && (ip6tables -C INPUT -p ${proto} --dport ${port} -j ACCEPT 2>/dev/null || ip6tables -I INPUT 4 -p ${proto} --dport ${port} -j ACCEPT)
    done

    [ "$has_firewalld" -eq 1 ] && firewall-cmd --reload >/dev/null 2>&1

    # 规则持久化
    if command_exists rc-service 2>/dev/null; then
        [ "$has_iptables" -eq 1 ] && iptables-save > /etc/iptables/rules.v4 2>/dev/null
        [ "$has_ip6tables" -eq 1 ] && ip6tables-save > /etc/iptables/rules.v6 2>/dev/null
    else
        if ! command_exists netfilter-persistent; then
            manage_packages install iptables-persistent || yellow "请手动安装netfilter-persistent或保存iptables规则" 
            netfilter-persistent save >/dev/null 2>&1
        elif command_exists service; then
            service iptables save 2>/dev/null
            service ip6tables save 2>/dev/null
        fi
    fi
}

# 下载并安装 sing-box 和 argo
install_singbox() {
    clear
    purple "正在安装 sing-box 中，请稍后..."
    ARCH_RAW=$(uname -m)
    case "${ARCH_RAW}" in
        'x86_64') ARCH='amd64';;
        'aarch64' | 'arm64') ARCH='arm64';;
        *) red "不支持的架构: ${ARCH_RAW}"; exit 1;;
    esac
    
    mkdir -p "${work_dir}"
    curl -sLo "${work_dir}/sing-box" "https://$ARCH.ssss.nyc.mn/sbx"
    curl -sLo "${work_dir}/argo" "https://$ARCH.ssss.nyc.mn/bot"
    chmod +x "${work_dir}/sing-box" "${work_dir}/argo"

    # 生成凭证
    local uuid="${UUID:-$(cat /proc/sys/kernel/random/uuid)}"
    local password=$(head -c 16 /dev/urandom | base64)
    local vless_port=${IN_PORT}
    local socks_port=$((IN_PORT + 1))
    local tuic_port=$((IN_PORT + 2))
    local hy2_port=$((IN_PORT + 3))
    local socks_user="yutian"
    local socks_pass="yutian=abcd"
    local output=$("${work_dir}/sing-box" generate reality-keypair)
    local private_key=$(echo "${output}" | awk '/PrivateKey:/ {print $2}')
    local public_key=$(echo "${output}" | awk '/PublicKey:/ {print $2}')
    echo "${public_key}" > "${pub_key_file}"
    
    # 放行端口
    allow_port $vless_port/tcp $socks_port/tcp $tuic_port/udp $hy2_port/udp > /dev/null 2>&1

    # 生成自签名证书
    openssl ecparam -genkey -name prime256v1 -out "${work_dir}/private.key"
    openssl req -new -x509 -days 3650 -key "${work_dir}/private.key" -out "${work_dir}/cert.pem" -subj "/CN=bing.com"

    # 检测网络类型并设置DNS策略
    dns_strategy=$(ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 && echo "prefer_ipv4" || (ping -c 1 -W 3 2001:4860:4860::8888 >/dev/null 2>&1 && echo "prefer_ipv6" || echo "prefer_ipv4"))

    # 拼接入站规则为数组
    declare -a inbounds_array=()

    # VLESS 入站规则
    if [[ -n "$VL_PORT" ]]; then
        inbounds_array+=( "$(jq -n \
            --argjson port "$vless_port" --arg uuid "$uuid" --arg pk "$private_key" \
            '{"type":"vless","tag":"vless-in","listen":"::","listen_port":$port,"users":[{"uuid":$uuid,"flow":"xtls-rprx-vision"}],"tls":{"enabled":true,"server_name":"www.iij.ad.jp","reality":{"enabled":true,"handshake":{"server":"www.iij.ad.jp","server_port":443},"private_key":$pk}}}')"
    fi

    # VMess (Argo) 入站规则
    inbounds_array+=( "$(jq -n \
        --argjson port "$ARGO_PORT" --arg uuid "$uuid" \
        '{"type":"vmess","tag":"vmess-in","listen":"::","listen_port":$port,"users":[{"uuid":$uuid}],"transport":{"type":"ws","path":"/vmess-argo"}}')"

    # SOCKS 入站规则
    if [[ -n "$SK_PORT" ]]; then
        inbounds_array+=( "$(jq -n \
            --argjson port "$socks_port" --arg user "$socks_user" --arg pass "$socks_pass" \
            '{"type":"socks","tag":"socks-in","listen":"::","listen_port":$port,"users":[{"username":$user,"password":$pass}]}')"
    fi

    # Hysteria2 入站规则
    if [[ -n "$HY_PORT" ]]; then
        inbounds_array+=( "$(jq -n \
            --argjson port "$hy2_port" --arg uuid "$uuid" \
            '{"type":"hysteria2","tag":"hysteria2-in","listen":"::","listen_port":$port,"users":[{"password":$uuid}],"tls":{"enabled":true,"alpn":["h3"],"certificate_path":"/etc/sing-box/cert.pem","key_path":"/etc/sing-box/private.key"}}')"
    fi

    # TUIC 入站规则
    if [[ -n "$TU_PORT" ]]; then
        inbounds_array+=( "$(jq -n \
            --argjson port "$tuic_port" --arg uuid "$uuid" --arg pass "$password" \
            '{"type":"tuic","tag":"tuic-in","listen":"::","listen_port":$port,"users":[{"uuid":$uuid,"password":$pass}],"tls":{"enabled":true,"alpn":["h3"],"certificate_path":"/etc/sing-box/cert.pem","key_path":"/etc/sing-box/private.key"}}')"
    fi

    # 将数组中的 JSON 字符串用逗号连接
    inbounds_json=$(printf ",%s" "${inbounds_array[@]}")
    inbounds_json=${inbounds_json:1}

    # 写入基础配置文件
    cat > "${config_dir}" << EOF
{
  "log": { "level": "info", "output": "/etc/sing-box/sb.log", "timestamp": true },
  "dns": { "servers": [{ "tag": "local", "address": "local", "strategy": "$dns_strategy" }] },
  "ntp": { "enabled": true, "server": "time.apple.com", "server_port": 123, "interval": "30m" },  
  "inbounds": [ ${inbounds_json} ],
  "outbounds": [
    { "tag": "direct", "type": "direct" },
    { "tag": "block", "type": "block" },
    {
      "tag": "warp-out",
      "type": "wireguard",
      "server": "engage.cloudflareclient.com",
      "server_port": 2408,
      "local_address": [ "172.16.0.2/32", "2606:4700:110:812a:4929:7d2a:af62:351c/128" ],
      "private_key": "gBthRjevHDGyV0KvYwYE52NIPy29sSrVr6rcQtYNcXA=",
      "peer_public_key": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo="
    }
  ],
  "route": {
    "rule_set": [
      {
        "tag": "openai",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/sing/geo-lite/geosite/openai.srs",
        "download_detour": "direct"
      },
      {
        "tag": "netflix",
        "type": "remote",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/sing/geo-lite/geosite/netflix.srs",
        "download_detour": "direct"
      }
    ],
    "rules": [
      {
        "domain_suffix": ["gemini.google.com", "grok.com"],
        "outbound": "wireguard-out"
      },
      {
        "rule_set": ["openai", "netflix"],
        "outbound": "wireguard-out"
      }
    ],
    "final": "direct"
  }
}
EOF
}

# 生成Argo启动命令 (可复用函数)
generate_argo_command() {
    local system_type=$1 # 接收 "systemd" 或 "openrc"
    local argo_cmd=""

    if [[ -n "$ARGO_DOMAIN" && -n "$ARGO_AUTH" ]]; then
        yellow "检测到ARGO环境变量，启用固定隧道模式"
        if [[ $ARGO_AUTH =~ TunnelSecret ]]; then
            # JSON 逻辑
            echo "$ARGO_AUTH" > "${work_dir}/tunnel.json"
            local tunnel_id=$(jq -r .TunnelID <<< "$ARGO_AUTH")
            cat > "${work_dir}/tunnel.yml" << EOF
tunnel: $tunnel_id
credentials-file: ${work_dir}/tunnel.json
protocol: http2
ingress:
  - hostname: $ARGO_DOMAIN
    service: http://localhost:$ARGO_PORT
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF
            argo_cmd="/etc/sing-box/argo tunnel --edge-ip-version auto --config /etc/sing-box/tunnel.yml run"
        else
            argo_cmd="/etc/sing-box/argo tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token '$ARGO_AUTH'"
        fi
    else
        yellow "未检测到ARGO环境变量，启用临时隧道模式"
        argo_cmd="/etc/sing-box/argo tunnel --url http://localhost:$ARGO_PORT --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1"
    fi

    # 根据系统类型，输出最终格式化的命令
    if [[ "$system_type" == "systemd" ]]; then
        echo "/bin/sh -c \"$argo_cmd\""
    elif [[ "$system_type" == "openrc" ]]; then
        echo "-c '$argo_cmd'"
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

    local argo_exec_start=$(generate_argo_command "systemd")

    cat > /etc/systemd/system/argo.service << EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target
[Service]
Type=simple
NoNewPrivileges=yes
TimeoutStartSec=0
ExecStart=${argo_exec_start}
Restart=on-failure
RestartSec=5s
[Install]
WantedBy=multi-user.target
EOF

    if [ -f /etc/centos-release ]; then
        yum install -y chrony
        systemctl start chronyd && systemctl enable chronyd
        chronyc -a makestep
        yum update -y ca-certificates
        bash -c 'echo "0 0" > /proc/sys/net/ipv4/ping_group_range'
    fi
    systemctl daemon-reload
    systemctl enable --now sing-box
    systemctl enable --now argo
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

    local argo_command_args=$(generate_argo_command "openrc")

    cat > /etc/init.d/argo << EOF
#!/sbin/openrc-run
description="Cloudflare Tunnel"
command="/bin/sh"
command_args="${argo_command_args}"
command_background=true
pidfile="/var/run/argo.pid"
EOF

    chmod +x /etc/init.d/sing-box /etc/init.d/argo
    rc-update add sing-box default
    rc-update add argo default
}

get_info() {
    clear
    local uuid=$(jq -r '.inbounds[0].users[0].uuid' "$config_dir" 2>/dev/null)
    local password=$(jq -r '.inbounds[] | select(.type == "tuic") | .users[].password' "$config_dir" 2>/dev/null)
    local public_key=$(cat "${pub_key_file}" 2>/dev/null)
    local socks_user=$(jq -r '.inbounds[] | select(.type == "socks") | .users[].username' "$config_dir" 2>/dev/null)
    local socks_pass=$(jq -r '.inbounds[] | select(.type == "socks") | .users[].password' "$config_dir" 2>/dev/null)
    
    server_ip=$(get_realip)
    isp=$(curl -s --max-time 2 https://speed.cloudflare.com/meta | awk -F\" '{print $26"-"$18}' | sed -e 's/ /_/g' || echo "vps")

    local argodomain
    if [[ -n "$ARGO_DOMAIN" ]]; then
        argodomain="$ARGO_DOMAIN"
        green "\n固定隧道域名: ${purple}$argodomain${re}\n"
    else
        for i in {1..5}; do
            purple "第 $i 次尝试获取Argo临时域名中..."
            argodomain=$(sed -n 's|.*https://\([^/]*trycloudflare\.com\).*|\1|p' "${work_dir}/argo.log")
            [ -n "$argodomain" ] && break
            sleep 2
        done
        [ -z "$argodomain" ] && red "获取Argo域名失败，请检查Argo服务日志！"
        green "\nArgo临时域名: ${purple}$argodomain${re}\n"
    fi
    
    > "${client_dir}"

    if [[ -n "$VL_PORT" ]]; then
        echo "vless://${uuid}@${server_ip}:${VL_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=chrome&pbk=${public_key}&type=tcp&headerType=none#${isp}" >> "${client_dir}"
    fi

    VMESS="{ \"v\": \"2\", \"ps\": \"${isp}\", \"add\": \"${CFIP}\", \"port\": \"${CFPORT}\", \"id\": \"${uuid}\", \"aid\": \"0\", \"scy\": \"none\", \"net\": \"ws\", \"type\": \"none\", \"host\": \"${argodomain}\", \"path\": \"/vmess-argo?ed=2048\", \"tls\": \"tls\", \"sni\": \"${argodomain}\", \"alpn\": \"\", \"fp\": \"randomized\"}"
    echo "vmess://$(echo "$VMESS" | base64 -w0)" >> "${client_dir}"

    if [[ -n "$HY_PORT" ]]; then
        echo "hysteria2://${uuid}@${server_ip}:${HY_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#${isp}" >> "${client_dir}"
    fi

    if [[ -n "$TU_PORT" ]]; then
        echo "tuic://${uuid}:${password}@${server_ip}:${TU_PORT}?sni=www.bing.com&congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#${isp}" >> "${client_dir}"
    fi

    if [[ -n "$SK_PORT" ]]; then
        echo "socks5://${socks_user}:${socks_pass}@${server_ip}:${SK_PORT}#${isp}" >> "${client_dir}"
    fi

    echo ""
    while IFS= read -r line; do echo -e "${purple}$line"; done < "${client_dir}"
    yellow "\n温馨提醒：Hysteria2/TUIC节点需打开客户端里的 “跳过证书验证”，或将节点的Insecure/allow_insecure设置为“true”\n"
    echo ""
}

start_singbox() {
    yellow "正在启动 ${server_name} 服务..."
    if [ -f /etc/alpine-release ]; then rc-service sing-box start; else systemctl start "${server_name}"; fi
    sleep 1
    check_singbox &>/dev/null; [[ $? -eq 0 ]] && green "${server_name} 启动成功" || red "${server_name} 启动失败"
}

stop_singbox() {
    yellow "正在停止 ${server_name} 服务..."
    if [ -f /etc/alpine-release ]; then rc-service sing-box stop; else systemctl stop "${server_name}"; fi
    sleep 1
    check_singbox &>/dev/null; [[ $? -eq 1 ]] && green "${server_name} 停止成功" || red "${server_name} 停止失败"
}

restart_singbox() {
    yellow "正在重启 ${server_name} 服务..."
    if [ -f /etc/alpine-release ]; then rc-service sing-box restart; else systemctl restart "${server_name}"; fi
    sleep 1
    check_singbox &>/dev/null; [[ $? -eq 0 ]] && green "${server_name} 重启成功" || red "${server_name} 重启失败"
}

start_argo() {
    yellow "正在启动 Argo 服务..."
    if [ -f /etc/alpine-release ]; then rc-service argo start; else systemctl start argo; fi
    sleep 1
    check_argo &>/dev/null; [[ $? -eq 0 ]] && green "Argo 启动成功" || red "Argo 启动失败"
}

stop_argo() {
    yellow "正在停止 Argo 服务..."
    if [ -f /etc/alpine-release ]; then rc-service argo stop; else systemctl stop argo; fi
    sleep 1
    check_argo &>/dev/null; [[ $? -eq 1 ]] && green "Argo 停止成功" || red "Argo 停止失败"
}

restart_argo() {
    yellow "正在重启 Argo 服务..."
    if [ -f /etc/alpine-release ]; then rc-service argo restart; else systemctl restart argo; fi
    sleep 1
    check_argo &>/dev/null; [[ $? -eq 0 ]] && green "Argo 重启成功" || red "Argo 重启失败"
}

uninstall_singbox_silent() {
    yellow "检测到旧安装，正在静默卸载..."
    if [ -f /etc/alpine-release ]; then
        rc-service sing-box stop &>/dev/null
        rc-service argo stop &>/dev/null
    else
        systemctl stop sing-box &>/dev/null
        systemctl stop argo &>/dev/null
    fi
    rm -rf "${work_dir}"
    rm -f /usr/bin/sb
    green "静默卸载完成。"
}

uninstall_singbox() {
   reading "确定要卸载 sing-box 吗? (y/n): " choice
   case "${choice}" in
       y|Y)
           yellow "正在卸载 sing-box"
           if [ -f /etc/alpine-release ]; then
                rc-service sing-box stop && rc-update del sing-box default
                rc-service argo stop && rc-update del argo default
                rm -f /etc/init.d/sing-box /etc/init.d/argo
           else
                systemctl stop "${server_name}" 2>/dev/null && systemctl disable "${server_name}" 2>/dev/null
                systemctl stop argo 2>/dev/null && systemctl disable argo 2>/dev/null
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

create_shortcut() {
    cat > "/usr/bin/sb" << EOF
#!/bin/bash
bash <(curl -Ls https://raw.githubusercontent.com/yutian81/Keepalive/main/vps_nat5in1.sh) \$1
EOF
    chmod +x "/usr/bin/sb"
    if [ -s /usr/bin/sb ]; then
        green "\n快捷指令 sb 创建成功，可执行 sb 命令来管理服务\n"
    else
        red "\n快捷指令创建失败\n"
    fi
}

change_hosts() {
    sh -c 'echo "0 0" > /proc/sys/net/ipv4/ping_group_range'
    sed -i '1s/.*/127.0.0.1   localhost/' /etc/hosts
    sed -i '2s/.*/::1         localhost/' /etc/hosts
}

change_config() {
    clear
    green "1. 修改端口"
    skyblue "------------"
    green "2. 修改UUID"
    skyblue "------------"
    green "3. 修改Reality伪装域名"
    skyblue "------------"
    purple "4. 返回主菜单"
    skyblue "------------"
    reading "请输入选择: " choice
    case "${choice}" in
        1)
            purple "此脚本已适配NAT VPS模式，端口管理已移至脚本外部，通过环境变量控制。"
            yellow "如需修改，请在VPS服务商后台修改NAT映射，然后使用新的外部端口变量卸载并重装。"
            sleep 4
            ;;
        2)
            reading "\n请输入新的UUID (回车将自动生成): " new_uuid
            [ -z "$new_uuid" ] && new_uuid=$(cat /proc/sys/kernel/random/uuid)
            jq --arg u "$new_uuid" '
            .inbounds = [ .inbounds[] | 
                if .users then .users = [ .users[] | 
                    if .uuid then .uuid = $u else . end |
                    if .password and (.password | length > 20) then .password = $u else . end
                ] else . end ]
            ' "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
            restart_singbox
            get_info
            green "\n通用UUID已修改为：${purple}${new_uuid}${re}\n"
            ;;
        3) 
            clear
            green "\n1. www.joom.com\n2. www.stengg.com\n3. www.wedgehr.com\n4. www.cerebrium.ai\n5. www.nazhumi.com\n"
            reading "\n请输入新的Reality伪装域名(可自定义,回车将使用默认1): " new_sni
            case "$new_sni" in
                "") new_sni="www.joom.com" ;; "1") new_sni="www.joom.com" ;; "2") new_sni="www.stengg.com" ;;
                "3") new_sni="www.wedgehr.com" ;; "4") new_sni="www.cerebrium.ai" ;; "5") new_sni="www.nazhumi.com" ;;
            esac
            jq --arg new_sni "$new_sni" '
            (.inbounds[] | select(.type == "vless") | .tls.server_name) = $new_sni |
            (.inbounds[] | select(.type == "vless") | .tls.reality.handshake.server) = $new_sni
            ' "$config_dir" > "$config_dir.tmp" && mv "$config_dir.tmp" "$config_dir"
            restart_singbox
            get_info
            green "\nReality sni已修改为：${purple}${new_sni}${re}\n"
            ;;
        4) menu ;;
        *)  red "无效的选项！" ;;
    esac
}

manage_singbox() {
    clear
    purple "--- Sing-box 管理 ---"
    green "1. 启动"
    green "2. 停止"
    green "3. 重启"
    purple "4. 返回主菜单"
    reading "\n请输入选择: " choice
    case "${choice}" in
        1) start_singbox ;;
        2) stop_singbox ;;
        3) restart_singbox ;;
        4) return ;;
        *) red "无效的选项！" ;;
    esac
}

manage_argo() {
    clear
    purple "--- Argo 隧道管理 ---"
    green "1. 启动"
    green "2. 停止"
    green "3. 重启"
    green "4. 添加Argo固定隧道"
    green "5. 切换回Argo临时隧道"
    purple "6. 返回主菜单"
    reading "\n请输入选择: " choice
    case "${choice}" in
        1) start_argo ;;
        2) stop_argo ;;
        3) restart_argo ;;
        4)
            clear
            yellow "\n固定隧道可为json或token，端口为${ARGO_PORT}，请自行在Cloudflare后台设置\n"
            purple "获取JSON地址：https://fscarmen.cloudflare.now.cc\n"
            reading "请输入你的argo域名: " argo_domain
            local ArgoDomain=$argo_domain
            reading "请输入你的argo密钥(token或json): " argo_auth

            if [[ $argo_auth =~ TunnelSecret ]]; then
                # JSON 逻辑
                local temp_argo_auth=$ARGO_AUTH
                export ARGO_DOMAIN=$argo_domain
                export ARGO_AUTH=$argo_auth
                if [ -f /etc/alpine-release ]; then alpine_openrc_services; else main_systemd_services; fi
                export ARGO_AUTH=$temp_argo_auth
            elif [[ $argo_auth =~ ^[A-Z0-9a-z=]{120,250}$ ]]; then
                # TOKEN 逻辑
                local temp_argo_auth=$ARGO_AUTH
                export ARGO_DOMAIN=$argo_domain
                export ARGO_AUTH=$argo_auth
                if [ -f /etc/alpine-release ]; then alpine_openrc_services; else main_systemd_services; fi
                export ARGO_AUTH=$temp_argo_auth # 还原
            else
                red "argo密钥格式不正确，请重新输入"; sleep 2; return
            fi
            restart_argo; change_argo_domain_manual "$ArgoDomain"
            ;;
        5)
            clear
            export ARGO_DOMAIN=""
            export ARGO_AUTH=""
            if [ -f /etc/alpine-release ]; then alpine_openrc_services; else main_systemd_services; fi
            get_quick_tunnel; change_argo_domain
            ;;
        6) return ;;
        *) red "无效的选项！" ;;
    esac
}

get_quick_tunnel() {
    restart_argo
    yellow "正在获取临时argo域名，请稍等...\n"
    local argo_domain_local
    for i in {1..5}; do
        purple "第 $i 次尝试获取ArgoDomain..."
        argo_domain_local=$(sed -n 's|.*https://\([^/]*trycloudflare\.com\).*|\1|p' "${work_dir}/argo.log")
        [ -n "$argo_domain_local" ] && break
        sleep 2
    done
    if [ -z "$argo_domain_local" ]; then red "获取临时隧道失败！请检查argo日志。"; else green "ArgoDomain：${purple}$argo_domain_local${re}\n"; fi
}

change_argo_domain_manual() {
    local argo_domain_local=$1
    if [ -z "$argo_domain_local" ] || [ ! -f "$client_dir" ]; then
        red "Argo域名为空或链接文件不存在，无法更新。"
        return
    fi
    vmess_line=$(grep 'vmess://' "$client_dir")
    if [ -n "$vmess_line" ]; then
        encoded_part=$(echo "$vmess_line" | sed 's/vmess:\/\///')
        decoded_json=$(echo "$encoded_part" | base64 -d)
        updated_json=$(echo "$decoded_json" | jq --arg domain "$argo_domain_local" '.host = $domain | .sni = $domain')
        new_encoded_part=$(echo "$updated_json" | base64 -w0)
        sed -i "s|$encoded_part|$new_encoded_part|" "$client_dir"
        green "vmess节点已更新,请手动复制最新的vmess-argo节点"
        purple "vmess://$new_encoded_part\n"
    fi
}

change_argo_domain() {
    local argo_domain_local
    argo_domain_local=$(sed -n 's|.*https://\([^/]*trycloudflare\.com\).*|\1|p' "${work_dir}/argo.log")
    change_argo_domain_manual "$argo_domain_local"
}

check_nodes() {
    check_singbox &>/dev/null
    if [ $? -eq 2 ]; then
        yellow "sing-box 尚未安装或未运行,请先安装"
    else
        get_info
    fi
}

# 主菜单
menu() {
   check_singbox &>/dev/null; check_singbox=$?
   check_argo &>/dev/null; check_argo=$?

   check_singbox_status=$(check_singbox)
   check_argo_status=$(check_argo)
   clear
   echo ""
   purple "=== sing-box NAT VPS 定制版脚本 (基于老王脚本) ===\n"
   purple "---Argo--- 状态: ${check_argo_status}"
   purple "---singbox--- 状态: ${check_singbox_status}\n"
   green "1. 安装/重装 sing-box"
   red "2. 卸载 sing-box"
   echo "==============="
   green "3. sing-box管理"
   green "4. Argo隧道管理"
   echo "==============="
   green "5. 查看节点信息"
   green "6. 修改节点配置"
   echo "==============="
   purple "7. SSH综合工具箱"
   echo "==============="
   red "0. 退出脚本"
   echo "==============="
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
            if [[ -z "$VL_PORT" && -z "$SK_PORT" && -z "$TU_PORT" && -z "$HY_PORT" ]]; then
                red "错误：您必须至少通过环境变量指定一个外部端口才能进行安装！"
                yellow "用法示例: "
                purple "export VL_PORT=49752 bash <(curl ...)"
                sleep 5
                continue
            fi
            
            check_singbox &>/dev/null
            if [ $? -ne 2 ]; then
                uninstall_singbox_silent
            fi

            manage_packages install jq tar openssl iptables curl
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
                red "不支持的初始化系统"; exit 1
            fi

            sleep 5
            get_info
            create_shortcut
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
