# Rede — configuração completa

Como o sistema é acessado e protegido em nível de rede: da LAN de casa
ao acesso remoto de fora, via WireGuard.

## 1. Rede local (LAN) de casa

- O painel físico (`panel/`) só é alcançável dentro da mesma rede Wi-Fi/
  Ethernet do notebook — não há exposição direta à internet (ver o
  modelo de confiança em [panel/ARCHITECTURE.md](panel/ARCHITECTURE.md)).
- A descoberta de dispositivos na LAN (nmap/ARP/mDNS) roda via WSL — ver
  [ARCHITECTURE.md](ARCHITECTURE.md#controle-de-rede-local-e-detecção-de-invasão-wsl-kali).
- **Nunca** faça port-forward da porta 8090 (ou qualquer porta do painel)
  no roteador para a internet — quem precisa de acesso de fora de casa
  deve entrar pela VPN (próxima seção), não por exposição direta.

## 2. Acesso remoto via WireGuard

Para acessar a rede de casa (ou recursos da VPS) a partir do celular fora
do Wi-Fi doméstico, a solução é um túnel **WireGuard** dedicado — rápido,
moderno, e com superfície de ataque muito menor que abrir portas
individualmente.

**Como está montado neste projeto:** existe uma interface WireGuard
dedicada só para o acesso do celular (separada de qualquer outra VPN que
outros projetos na mesma VPS possam usar) — isolar por interface/túnel
evita que um comprometimento de uma ponta afete as outras.

### Passo a passo para montar o seu

```bash
# 1. instalar o WireGuard (na VPS ou no roteador/servidor que fará de gateway)
sudo apt install wireguard

# 2. gerar o par de chaves do servidor
wg genkey | tee server_private.key | wg pubkey > server_public.key

# 3. gerar o par de chaves do cliente (o celular)
wg genkey | tee phone_private.key | wg pubkey > phone_public.key

# 4. configurar a interface do servidor (ex: /etc/wireguard/wgphone.conf)
```

```ini
[Interface]
Address = 10.66.0.1/24
ListenPort = 51820
PrivateKey = <server_private.key>

[Peer]
# o celular
PublicKey = <phone_public.key>
AllowedIPs = 10.66.0.2/32
```

```bash
# 5. subir a interface
sudo wg-quick up wgphone

# 6. manter no boot
sudo systemctl enable wg-quick@wgphone
```

No celular, o app oficial do WireGuard usa um perfil equivalente
(`[Interface]` com a chave privada do celular e o IP `10.66.0.2/24`;
`[Peer]` apontando para a chave pública do servidor, o `Endpoint` público
da VPS/roteador, e `AllowedIPs` cobrindo as sub-redes que você quer
alcançar por dentro do túnel — só a rede de casa, ou também a rede
interna da VPS, dependendo do que você precisa acessar remotamente).

**Nunca** commite os arquivos `.conf` reais (chaves privadas) em nenhum
repositório, público ou privado — trate cada `PrivateKey` como uma senha.
Os valores acima são exemplo/placeholder.

### Verificação

```bash
sudo wg show
# deve listar o peer do celular com "latest handshake" recente quando
# conectado, e contadores de bytes trocados
```

## 3. Isolamento entre projetos na mesma VPS

Se a VPS hospeda mais de um projeto (o autor também roda outros
sistemas na mesma máquina), vale manter interfaces WireGuard separadas
por finalidade (uma para o celular pessoal, outra para qualquer outro
uso) em vez de uma única VPN compartilhada — assim, revogar acesso de
uma ponta (perdeu o celular, por exemplo) não exige reconfigurar nada
que não seja aquele túnel específico.
