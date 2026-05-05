"""
Nekretnine.rs XML feed format.
Spec: https://www.nekretnine.rs/agencije/xml-feed (partnerski nalog)

tip_nekretnine:
  stan     -> stan
  kuca     -> kuca
  poslovni -> poslovni-prostor
  plac     -> plac

tip_oglasa:
  prodaja -> prodaja
  zakup   -> iznajmljivanje
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom


_TYPE = {
    "stan":     "stan",
    "kuca":     "kuca",
    "poslovni": "poslovni-prostor",
    "plac":     "plac",
}

_OFFER = {
    "prodaja": "prodaja",
    "zakup":   "iznajmljivanje",
}


def build_xml(agency: dict, listings: list[dict]) -> bytes:
    root = ET.Element("nekretnine")
    root.set("verzija", "3.0")

    for l in listings:
        nek = ET.SubElement(root, "nekretnina")
        ET.SubElement(nek, "sifra").text           = l.get("ref_number") or str(l["id"])[:8]
        ET.SubElement(nek, "tip_nekretnine").text  = _TYPE.get(l["type"], l["type"])
        ET.SubElement(nek, "tip_oglasa").text      = _OFFER.get(l["transaction"], l["transaction"])
        ET.SubElement(nek, "naslov").text          = l["title"]
        ET.SubElement(nek, "opis").text            = l.get("description") or ""
        ET.SubElement(nek, "cena").text            = str(int(l["price"]))
        ET.SubElement(nek, "valuta").text          = l.get("currency", "EUR")
        ET.SubElement(nek, "povrsina").text        = str(l["area_m2"])
        ET.SubElement(nek, "grad").text            = l["city"]
        ET.SubElement(nek, "opstina").text         = l.get("municipality") or ""
        ET.SubElement(nek, "adresa").text          = l.get("street") or ""

        if l.get("rooms") is not None:
            ET.SubElement(nek, "broj_soba").text = str(l["rooms"])
        if l.get("floor") is not None:
            ET.SubElement(nek, "sprat").text = str(l["floor"])
        if l.get("total_floors") is not None:
            ET.SubElement(nek, "broj_spratova").text = str(l["total_floors"])
        if l.get("year_built") is not None:
            ET.SubElement(nek, "godina_gradnje").text = str(l["year_built"])

        ET.SubElement(nek, "grejanje").text        = l.get("heating") or ""
        ET.SubElement(nek, "parking").text         = "da" if l.get("parking") else "ne"
        ET.SubElement(nek, "lift").text            = "da" if l.get("elevator") else "ne"
        ET.SubElement(nek, "namesteno").text       = l.get("furnished") or "nije"

        fotografije = ET.SubElement(nek, "fotografije")
        for url in (l.get("images") or []):
            ET.SubElement(fotografije, "fotografija").text = url

    return _pretty(root)


def _pretty(root: ET.Element) -> bytes:
    raw = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(raw)
    return dom.toprettyxml(indent="  ", encoding="UTF-8")
