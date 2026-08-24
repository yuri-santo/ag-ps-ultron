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

## 3. O celular do painel também é um nó Linux completo

Além de rodar a PWA do painel num navegador, o mesmo celular físico roda
um **userland Linux completo dentro do Android** (via um app estilo
UserLAnd/proot, sem root), com um servidor SSH leve (dropbear) escutando
numa porta alternativa. Esse userland entra na mesma interface WireGuard
do celular (`wgphone`) — então, de dentro da VPS, o agente consegue abrir
uma sessão SSH diretamente no celular e rodar comandos nele, não só
receber toques na PWA.

```bash
# exemplo (chave dedicada, porta alternativa do dropbear)
ssh -i ~/.ssh/chave_celular -p <PORTA_DROPBERD> usuario@<IP_DO_CELULAR_NA_VPN>
```

Isso é útil para automações que precisam rodar "de dentro" do celular
(não só disparadas por ele) — mas também é uma superfície de ataque a
mais: trate a chave SSH do celular e o `dropbear` com o mesmo cuidado de
qualquer outro servidor exposto (chave forte, sem senha, `PermitRootLogin
no` equivalente, atualização do userland em dia).

## 4. Túnel SSH reverso: a VPS alcançando o notebook

Separado do WireGuard, existe um **túnel SSH reverso** do notebook até a
VPS — o notebook, de dentro de casa, abre uma conexão de saída para a
VPS e pede para ela redirecionar uma porta local de volta para o próprio
notebook (`ssh -R`). Isso permite que a VPS "alcance" o notebook mesmo
sem o notebook ter IP público nem qualquer porta aberta no roteador de
casa — a conexão é sempre iniciada de dentro para fora.

```bash
# rodando NO NOTEBOOK, mantém a VPS com acesso de volta numa porta local dela
ssh -R <PORTA_TUNEL>:localhost:22 -N -i ~/.ssh/chave_reversa usuario@sua-vps
```

Na VPS, isso vira uma skill do agente que roda comandos ou lê arquivos
do notebook por esse túnel (`ssh -p <PORTA_TUNEL> usuario@localhost
"<comando>"`) — é o mecanismo por trás de qualquer automação que precise
tocar no sistema de arquivos ou rodar algo diretamente no Windows do
notebook a partir do agente. Para manter esse túnel sempre ativo (ele cai
se a rede de casa cair), use `autossh` ou um serviço systemd com restart
automático em vez de um `ssh -R` manual.

**Nunca** deixe essa porta redirecionada acessível para além do
`localhost` da VPS (evite `-R 0.0.0.0:porta:...`) — o objetivo é a VPS
falar com o notebook, não o mundo inteiro.

## 5. Pentest ativo contra a própria rede, a partir da VPS

Um container Kali dedicado roda **na própria VPS** (separado do WSL Kali
do notebook), com ferramental de pentest ativo (`nmap`, `hydra`,
`gobuster`, `dirb`, `nikto`, `sqlmap`, `netcat`, `sshpass`). Como a VPS
alcança a rede de casa pelos túneis acima (reverso para o notebook,
WireGuard para o celular), esse container consegue testar de verdade a
segurança dos próprios dispositivos domésticos — não só descobrir o que
existe, mas tentar validar o quão exposto está (força bruta de senha,
enumeração de diretório web, scan de vulnerabilidade), sob demanda e
contra a própria rede.

```bash
# exemplos (wrapper que roda o comando dentro do container Kali da VPS)
kali nmap -sV -p 1-1000 <IP_DO_ALVO_NA_VPN>
kali nikto -h <IP_DO_ALVO_NA_VPN>
```

Use esse ferramental só contra dispositivos que você mesmo possui e
autoriza testar — mesmo sendo "sua própria rede", ferramentas como
`hydra`/`sqlmap` são de força bruta/exploração ativa e podem derrubar um
serviço frágil (ex: uma câmera IP barata) sem querer.

## 6. Isolamento entre projetos na mesma VPS

Se a VPS hospeda mais de um projeto (o autor também roda outros
sistemas na mesma máquina), vale manter interfaces WireGuard separadas
por finalidade (uma para o celular pessoal, outra para qualquer outro
uso) em vez de uma única VPN compartilhada — assim, revogar acesso de
uma ponta (perdeu o celular, por exemplo) não exige reconfigurar nada
que não seja aquele túnel específico.
