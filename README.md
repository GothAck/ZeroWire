# zerowire

Zeroconf automagical wireguard tunnels for machines to automate away having to set up tunnels to hosts in networks you frequent.

## Why?
I wanted a way to bulk encrypt traffic between my development machine and other hosts on my home network, without concern for X509 certs, daemons needing to support TLS, and such annoyances.
Wouldn't it be great if when my dev machine and my rpi are on the same network they just created a WireGuard tunnel? Just like my firey printer, or my Chromecasts...

## How?
Install this package, create a simple /etc/security/zerowire.conf (chmod 0600), start in whatever way you usually run your daemons.
IPv6 is used inside the tunnels to allow for as many hosts as the universe can give you, IPv4 (and theoretically, untested) IPv6 can be used on your local "carrier" network.

Internal IPv6 addresses are allowed as per RFC 4193's fd00::/8:
fd [prefix]:[subnet]:[addr]


## /etc/security/zerowire.conf
```yaml
zero: # WireGuard interface wg-zero
  # Common to all your hosts:
  prefix: '10b24e7198' # See addressing above
  subnet: '0000' # See addressing above
  psk: 'S0/KiS28cN2ZH25/PWPzVCV5yG1q980sKW0oAYup4wM=' # Common secret, used to authenticate hosts and mdns services

  # Unique to each host
  addr: '8ad789f4c0dd16ea' # Address in your private IPv6 network
  privkey: 'MChrMqE3Aanb26K2q3k1sxA1Ls577wptpGnK8/NHxWY='
  pubkey: '4T7IpKzwFODBZZruvNXawH7+Sr0bU5kYAslQ1LyS+FE='
```


## What about feature xyz?
Open an issue, even better, open a pull request!

## Future plans?
- Tidy things up.
- Re-enable initial config file generator.
- Ability to accept/deny new hosts somewhat like SSH.
- Services advertized privately over the tunnel (fs mounts, web services, etc.).
- Local firewall config?
