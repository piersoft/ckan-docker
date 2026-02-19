# -*- coding: utf-8 -*-
from lxml import etree

# OAI DataCite 1.1 namespace
NS_OAI_DATACITE = "http://schema.datacite.org/oai/oai-1.1/"
NS_DATACITE_44 = "http://datacite.org/schema/kernel-4"
XSI = "http://www.w3.org/2001/XMLSchema-instance"


def _t(parent, tag, text, ns=None, **attrs):
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    if ns:
        el = etree.SubElement(parent, f"{{{ns}}}{tag}", **{k: str(v) for k, v in attrs.items()})
    else:
        el = etree.SubElement(parent, tag, **{k: str(v) for k, v in attrs.items()})
    el.text = text
    return el

def oai_datacite_writer(element, metadata):
    """
    pyoai writer: receives an lxml element (the <metadata> container)
    and a dict-like metadata object from CKANServer._record_for_dataset().
    """
    md = getattr(metadata, "_map", None)
    if md is None:
      # fallback: prova altre varianti
      md = getattr(metadata, "map", None) or getattr(metadata, "data", None)

    if md is None:
      # ultimo fallback: prova a ricostruire da keys() se esistono
      try:
        md = {k: metadata.getField(k) for k in metadata.getFields()}
      except Exception:
        md = {}

        # fallback: some versions store items in .data or .map
        md = getattr(metadata, "data", None) or getattr(metadata, "map", None) or {}
    # wrapper oai_datacite:oai_datacite
    nsmap = {"oai_datacite": NS_OAI_DATACITE, "xsi": XSI, "datacite": NS_DATACITE_44}
    root = etree.SubElement(element, f"{{{NS_OAI_DATACITE}}}oai_datacite", nsmap=nsmap)

    # recommended fields for wrapper
    _t(root, "schemaVersion", "1.1", ns=NS_OAI_DATACITE)

    payload = etree.SubElement(root, f"{{{NS_OAI_DATACITE}}}payload")

    # ---- DataCite payload (Kernel 4.x) ----
    res = etree.SubElement(payload, f"{{{NS_DATACITE_44}}}resource", nsmap={"xsi": XSI})
    res.set(f"{{{XSI}}}schemaLocation", f"{NS_DATACITE_44} http://schema.datacite.org/meta/kernel-4.4/metadata.xsd")

    # identifier: prefer a real URL if present
    ids = md.get("identifier") or []

    if not isinstance(ids, (list, tuple)):
        ids = [ids]

    ident_val = None

    # prima cerca una URL vera
    for x in ids:
        s = str(x).strip()
        if s.startswith("http://") or s.startswith("https://"):
            ident_val = s
            break

    # fallback: primo valore non vuoto
    if not ident_val:
        for x in ids:
            s = str(x).strip()
            if s and s != "[]":
                ident_val = s
                break

    ident = etree.SubElement(res, f"{{{NS_DATACITE_44}}}identifier")

    if ident_val and ident_val.startswith(("http://", "https://")):
        ident.set("identifierType", "URL")
    else:
        ident.set("identifierType", "Local")

    ident.text = ident_val or ""

    # creators
    creators = etree.SubElement(res, f"{{{NS_DATACITE_44}}}creators")
    creator_names = md.get("creator") or []
    if not isinstance(creator_names, (list, tuple)):
        creator_names = [creator_names]
    if not creator_names:
        creator_names = ["Unknown"]
    for name in creator_names:
        c = etree.SubElement(creators, f"{{{NS_DATACITE_44}}}creator")
        _t(c, "creatorName", name, ns=NS_DATACITE_44)

    # titles
    titles = etree.SubElement(res, f"{{{NS_DATACITE_44}}}titles")
    title_list = md.get("title") or []
    if not isinstance(title_list, (list, tuple)):
        title_list = [title_list]
    for t in title_list:
        _t(titles, "title", t, ns=NS_DATACITE_44)

    # publisher
    publishers = md.get("publisher") or []
    pub_val = None
    if isinstance(publishers, (list, tuple)) and publishers:
        pub_val = publishers[0]
    elif isinstance(publishers, str):
        pub_val = publishers
    _t(res, "publisher", pub_val or "CKAN", ns=NS_DATACITE_44)

    # publicationYear (fallback: year from date)
    pub_year = None
    dates = md.get("date") or []
    if isinstance(dates, (list, tuple)) and dates:
        pub_year = str(dates[0])[:4]
    _t(res, "publicationYear", pub_year or "2026", ns=NS_DATACITE_44)

    # resourceType
    rt = etree.SubElement(res, f"{{{NS_DATACITE_44}}}resourceType")
    rt.set("resourceTypeGeneral", "Dataset")
    rt.text = "Dataset"
    # subjects
    subjects_vals = md.get("subject") or []
    if not isinstance(subjects_vals, (list, tuple)):
        subjects_vals = [subjects_vals]
    subjects_vals = [str(x).strip() for x in subjects_vals if str(x).strip() and str(x).strip() != "[]"]
    if subjects_vals:
        subjects_el = etree.SubElement(res, f"{{{NS_DATACITE_44}}}subjects")
        for s in subjects_vals:
            _t(subjects_el, "subject", s, ns=NS_DATACITE_44)

    # rightsList
    rights_vals = md.get("rights") or []
    if not isinstance(rights_vals, (list, tuple)):
        rights_vals = [rights_vals]
    rights_vals = [str(x).strip() for x in rights_vals if str(x).strip() and str(x).strip() != "[]"]
    if rights_vals:
        rights_el = etree.SubElement(res, f"{{{NS_DATACITE_44}}}rightsList")
        for r in rights_vals:
            _t(rights_el, "rights", r, ns=NS_DATACITE_44)

    # descriptions (Abstract)
    desc_vals = md.get("description") or []
    if not isinstance(desc_vals, (list, tuple)):
        desc_vals = [desc_vals]
    desc_vals = [str(x).strip() for x in desc_vals if str(x).strip() and str(x).strip() != "[]"]
    if desc_vals:
        descs_el = etree.SubElement(res, f"{{{NS_DATACITE_44}}}descriptions")
        d = etree.SubElement(descs_el, f"{{{NS_DATACITE_44}}}description")
        d.set("descriptionType", "Abstract")
        d.text = desc_vals[0]

