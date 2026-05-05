"""
Halo oglasi XML feed format.
Spec: https://www.halooglasi.com/nekretnine/xml-feed (partnerski nalog)

Kategorije:
  stan -> Stanovi
  kuca -> Kuce i vile
  poslovni -> Poslovni prostori
  plac -> Placevi i okucnice

Transakcija:
  prodaja -> Prodaja
  zakup   -> Izdavanje
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom


_CATEGORY = {
    "stan":     "Stanovi",
    "kuca":     "Kuce i vile",
    "poslovni": "Poslovni prostori",
    "plac":     "Placevi i okucnice",
}

_TRANSACTION = {
    "prodaja": "Prodaja",
    "zakup":   "Izdavanje",
}


def build_xml(agency: dict, listings: list[dict]) -> bytes:
    root = ET.Element("halooglasi")
    root.set("version", "2.0")

    info = ET.SubElement(root, "agencija")
    ET.SubElement(info, "naziv").text = agency["name"]
    ET.SubElement(info, "email").text = agency.get("email", "")

    oglasi_el = ET.SubElement(root, "oglasi")

    for l in listings:
        og = ET.SubElement(oglasi_el, "oglas")
        ET.SubElement(og, "id").text           = str(l["id"])
        ET.SubElement(og, "ref").text          = l.get("ref_number") or str(l["id"])[:8]
        ET.SubElement(og, "kategorija").text   = _CATEGORY.get(l["type"], l["type"])
        ET.SubElement(og, "tip_oglasa").text   = _TRANSACTION.get(l["transaction"], l["transaction"])
        ET.SubElement(og, "naziv").text        = l["title"]
        ET.SubElement(og, "opis").text         = l.get("description") or ""
        ET.SubElement(og, "cena").text         = str(int(l["price"]))
        ET.SubElement(og, "valuta").text       = l.get("currency", "EUR")
        ET.SubElement(og, "kvadratura").text   = str(l["area_m2"])
        ET.SubElement(og, "grad").text         = l["city"]
        ET.SubElement(og, "opstina").text      = l.get("municipality") or ""
        ET.SubElement(og, "ulica").text        = l.get("street") or ""

        if l.get("rooms") is not None:
            ET.SubElement(og, "broj_soba").text = str(l["rooms"])
        if l.get("floor") is not None:
            ET.SubElement(og, "sprat").text = str(l["floor"])
        if l.get("total_floors") is not None:
            ET.SubElement(og, "ukupno_spratova").text = str(l["total_floors"])
        if l.get("year_built") is not None:
            ET.SubElement(og, "godina_izgradnje").text = str(l["year_built"])

        ET.SubElement(og, "grejanje").text     = l.get("heating") or ""
        ET.SubElement(og, "parking").text      = "da" if l.get("parking") else "ne"
        ET.SubElement(og, "lift").text         = "da" if l.get("elevator") else "ne"
        ET.SubElement(og, "namesteno").text    = l.get("furnished") or "nije"

        slike = ET.SubElement(og, "slike")
        for url in (l.get("images") or []):
            ET.SubElement(slike, "slika").text = url

    return _pretty(root)


def _pretty(root: ET.Element) -> bytes:
    raw = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(raw)
    return dom.toprettyxml(indent="  ", encoding="UTF-8")
