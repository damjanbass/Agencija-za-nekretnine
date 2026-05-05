"""
4zida.rs XML feed format.
Spec: https://www.4zida.rs/agencije/xml-uvoz (partnerski nalog)

propertyType:
  stan     -> apartment
  kuca     -> house
  poslovni -> commercial
  plac     -> land

offerType:
  prodaja -> sale
  zakup   -> rent
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom


_TYPE = {
    "stan":     "apartment",
    "kuca":     "house",
    "poslovni": "commercial",
    "plac":     "land",
}

_OFFER = {
    "prodaja": "sale",
    "zakup":   "rent",
}


def build_xml(agency: dict, listings: list[dict]) -> bytes:
    root = ET.Element("properties")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("version", "1.0")

    for l in listings:
        prop = ET.SubElement(root, "property")
        ET.SubElement(prop, "externalId").text    = l.get("ref_number") or str(l["id"])[:8]
        ET.SubElement(prop, "propertyType").text  = _TYPE.get(l["type"], l["type"])
        ET.SubElement(prop, "offerType").text     = _OFFER.get(l["transaction"], l["transaction"])
        ET.SubElement(prop, "title").text         = l["title"]
        ET.SubElement(prop, "description").text   = l.get("description") or ""
        ET.SubElement(prop, "price").text         = str(int(l["price"]))
        ET.SubElement(prop, "currency").text      = l.get("currency", "EUR")
        ET.SubElement(prop, "surfaceArea").text   = str(l["area_m2"])

        loc = ET.SubElement(prop, "location")
        ET.SubElement(loc, "city").text           = l["city"]
        ET.SubElement(loc, "municipality").text   = l.get("municipality") or ""
        ET.SubElement(loc, "street").text         = l.get("street") or ""

        if l.get("rooms") is not None:
            ET.SubElement(prop, "roomCount").text = str(l["rooms"])
        if l.get("floor") is not None:
            ET.SubElement(prop, "floor").text = str(l["floor"])
        if l.get("total_floors") is not None:
            ET.SubElement(prop, "totalFloors").text = str(l["total_floors"])
        if l.get("year_built") is not None:
            ET.SubElement(prop, "yearOfConstruction").text = str(l["year_built"])

        ET.SubElement(prop, "heating").text       = l.get("heating") or ""
        ET.SubElement(prop, "parking").text       = "true" if l.get("parking") else "false"
        ET.SubElement(prop, "elevator").text      = "true" if l.get("elevator") else "false"
        ET.SubElement(prop, "furnished").text     = l.get("furnished") or "nije"

        images_el = ET.SubElement(prop, "images")
        for url in (l.get("images") or []):
            ET.SubElement(images_el, "image").text = url

    return _pretty(root)


def _pretty(root: ET.Element) -> bytes:
    raw = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(raw)
    return dom.toprettyxml(indent="  ", encoding="UTF-8")
