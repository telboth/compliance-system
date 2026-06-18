"""
Kuratert liste over kjente logistikkselskaper world-wide.

Brukes i sanksjonsscreeningservicen for å unngå støy:
Domener på denne listen genererer IKKE sanksjonskandidatnavn fra domenedelen
av e-postadressen (f.eks. sender «info@dhl.com» ikke «dhl» til yente).
Local-partens navnehints (f.eks. «john doe» fra «john.doe@dhl.com»)
screenes fortsatt som normalt — kun domenet er whitelistet.

Kategorier:
  - Globale kurerer / pakkelevering
  - Rederier (ocean freight)
  - Flyfrakt / luftkargo
  - Speditører og 3PL (tredjepartslogistikk)
  - Vei- og jernbanegods
  - Havn og terminaldrift
  - Nordiske / norske aktører
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Globale kurerer og pakkelevering
# ---------------------------------------------------------------------------
_COURIERS: frozenset[str] = frozenset(
    {
        "fedex.com",
        "dhl.com",
        "dhl-freight.com",
        "dhl-express.com",
        "dhlfreight.com",
        "dhl-global-forwarding.com",
        "ups.com",
        "tnt.com",
        "dpd.com",
        "dpd.de",
        "dpd.fr",
        "dpd.co.uk",
        "dpd.nl",
        "dpd.be",
        "gls-group.eu",
        "gls-group.com",
        "gls.de",
        "gls.nl",
        "gls.be",
        "hermes.de",
        "myhermes.co.uk",
        "hermesworld.com",
        "parcelforce.com",
        "royalmail.com",
        "deutschepost.de",
        "laposte.fr",
        "postnl.nl",
        "bpost.be",
        "correos.es",
        "posteitaliane.it",
        "ptt.gov.tr",
        "auspost.com.au",
        "canadapost-postescanada.ca",
        "usps.com",
    }
)

# ---------------------------------------------------------------------------
# Rederier – ocean freight / shipping lines
# ---------------------------------------------------------------------------
_SHIPPING_LINES: frozenset[str] = frozenset(
    {
        "maersk.com",
        "sealandmaersk.com",
        "msc.com",
        "cma-cgm.com",
        "cmacgm.com",
        "evergreen-line.com",
        "evergreen-marine.com",
        "hapag-lloyd.com",
        "hapag.com",
        "one-line.com",
        "cosco.com",
        "coscogroup.com",
        "coscoshipping.com",
        "yangming.com",
        "hmm21.com",
        "hmm.co.kr",
        "pilship.com",
        "pil.com.sg",
        "zim.com",
        "ool.com.sg",
        "wanhai.com",
        "hanjin.com",
        "kmtc.co.kr",
        "t.t-line.com",
        "ttline.com",
        "finnlines.com",
        "stenaline.com",
        "dfds.com",
        "colorline.com",
        "polferries.pl",
        "tallink.com",
        "ssvcompany.com",
    }
)

# ---------------------------------------------------------------------------
# Flyfrakt / luftkargo
# ---------------------------------------------------------------------------
_AIR_FREIGHT: frozenset[str] = frozenset(
    {
        "cargolux.com",
        "lufthansa-cargo.com",
        "lufthansacargo.com",
        "dlh.de",
        "emiratesgroup.com",
        "skycargo.com",
        "qatarairways.com",
        "saudiaaircargo.com",
        "koreanair.com",
        "cathaypacific.com",
        "cathaypacificcargo.com",
        "airfranceklm.com",
        "airfrancecargo.com",
        "turkishairlines.com",
        "singairlines.com",
        "singaporeair.com",
        "silkway.az",
        "freighterairlines.com",
        "iag-cargo.com",
        "iagcargo.com",
        "fedex.com",  # dekket over — dobbel-listing OK
        "ups.com",  # UPS Airlines
        "atlas-air.com",
        "atlasair.com",
        "acmi.com",
        "menzies-aviation.com",
        "dnata.com",
    }
)

# ---------------------------------------------------------------------------
# Speditører og 3PL (tredjepartslogistikk)
# ---------------------------------------------------------------------------
_FREIGHT_FORWARDERS: frozenset[str] = frozenset(
    {
        "kuehne-nagel.com",
        "kn-portal.com",
        "dbschenker.com",
        "schenker.com",
        "dsv.com",
        "dsvpanalpina.com",
        "panalpina.com",
        "xpo.com",
        "xpologistics.com",
        "geodis.com",
        "bollore-logistics.com",
        "bollore.com",
        "ceva.com",
        "cevalogistics.com",
        "expeditors.com",
        "chrobinson.com",
        "siemenslogistics.com",
        "rhenus.com",
        "rhenus-logistics.com",
        "dachser.com",
        "agility.com",
        "agilitylogistics.com",
        "hellmannworldwide.com",
        "hellmann.net",
        "bolloretransport.com",
        "fiata.org",
        "dbgroup.com",
        "db-schenker.com",
        "baxglobal.com",
        "schnellecke.com",
        "logwin-logistics.com",
        "uti.com",
        "deugro.com",
        "cargotec.com",
        "flexport.com",
        "freightos.com",
        "shipbob.com",
        "fourwinds-logistics.com",
        "aramex.com",
        "nyklogistics.com",
        "jbhunt.com",
        "werner.com",
        "landstar.com",
        "echo.com",
        "coyote.com",
        "totalexpress.com.br",
        "matson.com",
        "crowley.com",
        "kirby.com",
    }
)

# ---------------------------------------------------------------------------
# Vei- og jernbanegods
# ---------------------------------------------------------------------------
_ROAD_RAIL: frozenset[str] = frozenset(
    {
        "dbcargo.com",
        "db-cargo.com",
        "db.com",
        "ralpin.com",
        "hupac.com",
        "kombiverkehr.de",
        "captrain.eu",
        "railcargo.com",
        "pkp-cargo.pl",
        "cargo.cz",
        "sncf.com",
        "sncflogistics.com",
        "rfi.it",
        "rne.eu",
        "waberer.hu",
        "dachser.com",  # vei + luft
        "dsv.com",  # vei + luft
        "lkwtransport.de",
        "toll.com",
        "asfreight.com",
        "norbert-dentressangle.com",
        "xpolog.com",
    }
)

# ---------------------------------------------------------------------------
# Havn og terminaldrift
# ---------------------------------------------------------------------------
_PORT_TERMINAL: frozenset[str] = frozenset(
    {
        "apmterminals.com",
        "apm.com",
        "hutchison-ports.com",
        "hutchisonports.com",
        "psa.com.sg",
        "psainternational.com",
        "dpworld.com",
        "eurogate.eu",
        "eurogate.de",
        "hhla.de",
        "hamiltonbrands.com",
        "ictsi.com",
        "terminalsone.com",
        "bremenports.de",
        "portofrotterdam.com",
        "portofantwerp.com",
        "hafen-hamburg.de",
        "portofhamburg.com",
        "kavecshamn.se",
    }
)

# ---------------------------------------------------------------------------
# Nordiske og norske aktører
# ---------------------------------------------------------------------------
_NORDIC: frozenset[str] = frozenset(
    {
        "bring.com",
        "postnord.com",
        "postnord.se",
        "postnord.dk",
        "postnord.fi",
        "posten.no",
        "postens.no",
        "posti.fi",
        "post.dk",
        "tollpostglobe.no",
        "tollpost.no",
        "schenker.no",
        "schenker.se",
        "schenker.dk",
        "schenker.fi",
        "nettlast.no",
        "helthjem.no",
        "klimax.no",
        "nor-cargo.no",
        "norcargo.no",
        "dfds.com",  # også nordisk
        "stenaline.com",
        "colorline.no",
        "colorline.com",
        "containerships.fi",
        "naviagrouplogistics.no",
        "naviaco.no",
        "nettbuss.no",
        "vy.no",
        "vygruppen.no",
        "cargonet.no",
        "greencarrier.com",
        "greencarrier.se",
        "logistikk.no",
        "asendia.com",
    }
)

# ---------------------------------------------------------------------------
# Diverse internasjonale / e-handel logistikk
# ---------------------------------------------------------------------------
_OTHER: frozenset[str] = frozenset(
    {
        "amazon.com",  # Amazon Logistics
        "amazon.co.uk",
        "amazon.de",
        "amazon.fr",
        "amazon.nl",
        "amazon.se",
        "amazon.no",
        "jd.com",  # JD Logistics (Kina)
        "jdlogistics.com",
        "sf-express.com",  # SF Express (Kina)
        "yunbao.com",
        "yanwen.com",
        "4px.com",
        "cainiao.com",  # Alibaba / Cainiao
        "nipost.com.ng",
        "emiratespost.ae",
        "flydubai.com",
        "cargo.ae",
        "posta.ro",
        "post.hr",
        "bpost.be",
        "an-post.ie",
        "postoffice.co.uk",
        "dhl.co.uk",
        "dhl.de",
        "dhl.nl",
        "dhl.fr",
        "dhl.it",
        "dhl.es",
        "dhl.pl",
        "dhl.se",
        "dhl.no",
        "dhl.dk",
        "dhl.fi",
        "fedex.eu",
        "ups.co.uk",
        "ups.de",
        "ups.fr",
        "ups.it",
        "ups.nl",
        "ups.se",
        "ups.no",
    }
)

# ---------------------------------------------------------------------------
# Eksportert samlet set — bruk dette i koden
# ---------------------------------------------------------------------------
LOGISTICS_DOMAINS: frozenset[str] = (
    _COURIERS | _SHIPPING_LINES | _AIR_FREIGHT | _FREIGHT_FORWARDERS | _ROAD_RAIL | _PORT_TERMINAL | _NORDIC | _OTHER
)


def is_logistics_domain(domain: str) -> bool:
    """Returner True dersom domenet tilhører et kjent logistikkselskap."""
    return domain.lower().lstrip("@") in LOGISTICS_DOMAINS
