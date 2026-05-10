# Zonneplan Negatief Uurprijs — StecaGrid 5513

Schakelt elke 15 minuten de teruglevering van een StecaGrid 5513 omvormer uit
wanneer de Zonneplan-uurprijs strikt negatief is, en zet 'm bij niet-negatieve
prijs weer op 5500 W.

## Setup op de Raspberry Pi

```bash
# 1. Clone
cd ~
git clone <jouw-fork-url> zonneplan-stecagrid-5513
cd zonneplan-stecagrid-5513

# 2. Virtual env + dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Config invullen (let op: config.yaml staat in .gitignore)
cp config.example.yaml config.yaml
nano config.yaml          # vul ip, password, max_watts in

# 4. Eenmalige Zonneplan-login (e-mail magic-link)
python fetch_prices.py
# -> voer e-mail in, klik op de link in je mailbox
# -> tokens worden opgeslagen in ~/.zonneplan_tokens.json

# 5. Smoke-test
python controller.py
# -> moet exit 0 geven, prijs + actie loggen op stdout

# 6. Cron toevoegen
crontab -e
# Voeg toe (één regel):
*/15 * * * * cd /home/pi/zonneplan-stecagrid-5513 && .venv/bin/python controller.py >> ~/zonneplan_prices.log 2>&1
```

## Hoe het werkt

- **Drempel:** strikt `< 0` €/kWh.
- **Cadans:** elke 15 minuten via cron.
- **Idempotent:** alleen schrijven als de huidige limit > 1 W afwijkt van de gewenste waarde.
- **Failsafe:** als het script ooit faalt terwijl de limit op 0 W staat, herstelt
  de eerstvolgende run met niet-negatieve prijs de waarde naar 5500 W.

## Bestanden

| File | Verantwoordelijkheid |
| --- | --- |
| `controller.py` | Main entrypoint (cron) |
| `decide.py` | Pure beslislogica |
| `fetch_prices.py` | Zonneplan API + tokens |
| `inverter.py` | Sync wrapper rond pykoplenti |
| `config.yaml` | Lokale config (niet in git) |

## Tests

```bash
pytest -v
```

## Troubleshooting

- **`ModuleNotFoundError: pykoplenti`** — `pip install -r requirements.txt` uitvoeren in de venv.
- **`Geen tokens`** — handmatig `python fetch_prices.py` draaien.
- **`AuthenticationException`** — wachtwoord in `config.yaml` klopt niet.
- **`ClientConnectorError`** — IP klopt niet of omvormer is niet bereikbaar.
- **Logfile** — `~/zonneplan_prices.log`.
