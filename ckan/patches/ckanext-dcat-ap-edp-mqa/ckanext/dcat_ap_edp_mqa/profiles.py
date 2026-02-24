from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, DCTERMS, SKOS

from ckanext.dcat.profiles import EuropeanDCATAP2Profile
from ckanext.dcat.profiles import DCAT, DCT, LOCN

from rdflib.term import Literal as RDFLiteral

from .vocabularies import vocabulary_providers

import logging
log = logging.getLogger(__name__)


class MqaEuropeanDCATAP2Profile(EuropeanDCATAP2Profile):
    """
    An RDF profile for the MQA EDP DCAT-AP recommendation for data portals
    It requires the European DCAT-AP profile (`euro_dcat_ap`)
    """


    def _safe_get_scheming_schema(self):
          try:
              h = toolkit.h
              if hasattr(h, "scheming_get_dataset_schema"):
                  return h.scheming_get_dataset_schema()
          except Exception:
              pass
          return None

    def _best_label(self, node, lang_preference=("it", "en")):
        """
        Safe label picker that works with ConjunctiveGraph too (no g.label()).
        """
        if not node:
            return None

        candidates = []
        for predicate in (SKOS.prefLabel, RDFS.label, DCTERMS.title):
            for o in self.g.objects(node, predicate):
                if isinstance(o, RDFLiteral):
                    candidates.append(o)

        if not candidates:
            return None

        for lang in lang_preference:
            for lit in candidates:
                if (lit.language or "").lower().startswith(lang):
                    return str(lit)

        return str(candidates[0])


    def parse_dataset(self, dataset_dict, dataset_ref):
        # lascia fare tutto al profilo EU prima
        super().parse_dataset(dataset_dict, dataset_ref)

        # --- Spatial label (robusto) ---
        spatial = self._object(dataset_ref, DCT.spatial)
        if spatial:
            spatial_label = self._best_label(spatial) or str(spatial)
            if spatial_label:
                dataset_dict.setdefault("extras", [])
                dataset_dict["extras"].append(
                    {"key": "spatial_text", "value": spatial_label}
                )

        return dataset_dict


    def graph_from_dataset(self, dataset_dict, dataset_ref):

        super().graph_from_dataset(dataset_dict, dataset_ref)
        
        g: Graph = self.g

        for s, p, o in g.triples((None, DCT.spatial, None)):
            # locn:geometry if available        
            location = g.value(o, LOCN["geometry"])
            if location:
                g.remove((s, p, o)) # remove dct:spatial
                g.remove((o, None, DCT.Location)) # remove dct:Location
                g.remove((o, LOCN.geometry, None)) # remove locn:geometry
                
                for l in location.split(","):
                    if l == "EUROPE": aux_o = "http://publications.europa.eu/resource/authority/continent/" + l
                    else: aux_o = "http://publications.europa.eu/resource/authority/country/" + l

                    # Create one object (<dct:spatial/>) for each location
                    g.add(
                        (
                            s,
                            p,
                            URIRef(aux_o)
                        )
                    )
            
        for s, p, o in g.triples((None, DCT.language, None)):  
            # dct:language if available        
            g.remove((s, p, o))
            g.add(
                (
                    s,
                    p,
                    URIRef("http://publications.europa.eu/resource/authority/language/" + o.split("/")[-1]) # URIRef(o) (already with url)
                )
            )
                
        # TODO: add vocabulary_providers
        for s, p, o in g.triples((None, DCT.accessRights, None)):
            # dct:accessRigths if available
            g.remove((s, p, o))
            g.add(
                (
                    s,
                    p,
                    URIRef("http://publications.europa.eu/resource/authority/access-right/" + o.split("/")[-1]) # URIRef(o) (already with url)
                )
            )

        for s, p, o in g.triples((None, DCAT.theme, None)):
            # dcat:theme if available
            g.remove((s, p, o))
            g.add(
                (
                    s,
                    p,
                    URIRef("http://publications.europa.eu/resource/authority/data-theme/" + o.split("/")[-1]) # URIRef(o) (already with url)
                )
            )
    
        for s, p, o in g.triples((None, RDF.type, DCAT.Distribution)):
            # dct:format if available
            format = g.value(s, DCT["format"])
            if format:
                g.remove((s, DCT["format"], None))
                g.add(
                    (
                        s,
                        DCT["format"],
                        vocabulary_providers.get("DataEurope").getUri(format),
                    )
                )

            # dcat:mediaType if available
            media = g.value(s, DCAT["mediaType"])
            if media:
                g.remove((s, DCAT["mediaType"], None))
                g.add(
                    (
                        s,
                        DCAT["mediaType"],
                        vocabulary_providers.get("IANA").getUri(media),
                    )
                )


            
            # # Availability
            # availability = resource_dict.get('availability')
            # if availability:
            #     g.add((distribution, DCATAP.availability,
            #            URIRefOrLiteral(availability)))

            # # conformsTo: change range to dct:Standard
            # self.generate_conforms_to_graph(distribution)

            # # rights: change range to dct:RightsStatement
            # self.add_rdf_type(distribution, DCT['rights'], DCT['RightsStatement'])

            # # page change range to foaf:Document
            # self.add_rdf_type(distribution, FOAF['page'], FOAF['Document'])

            # # dct:language change range to dct:LinguisticSystem
            # self.add_rdf_type(distribution, DCT['language'], DCT['LinguisticSystem'])

            # # adms:status change range to skos:Concept
            # self.add_rdf_type(distribution, ADMS['status'], SKOS['Concept'])

            # # dct:license change range to dct:LicenseDocument
            # self.add_rdf_type(distribution, DCT['license'], DCT['LicenseDocument'])
