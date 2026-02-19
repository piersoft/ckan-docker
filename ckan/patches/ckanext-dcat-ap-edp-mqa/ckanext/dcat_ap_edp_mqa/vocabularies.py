# TODO: It might be necessary to do the same with [Access right](https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?uri=http://publications.europa.eu/resource/dataset/access-right)
# and [licences](https://gitlab.com/european-data-portal/edp-vocabularies/-/blob/master/edp-licences-skos.rdf)
# Licences is something to be further analyzed as it depends on the language and
# it will be a bit more difficult as we have to search in `skos:altLabel` Literal.
# Then base on the text we can get the subject, which is the URI to include in the
# final DCAT-AP document

from .object_factory import ObjectFactory
from .dataeuropa_vocabulary import DataEuropaVocabularyBuilder
from .iana_vocabulary import IanaVocabularyBuilder


class VocabularyProvider(ObjectFactory):
    def get(self, service_id, **kwargs):
        return self.create(service_id, **kwargs)


vocabulary_providers = VocabularyProvider()
vocabulary_providers.register_builder("IANA", IanaVocabularyBuilder())
vocabulary_providers.register_builder("DataEurope", DataEuropaVocabularyBuilder())

# if __name__ == "__main__":

#     iana = vocabulary_providers.get("IANA").getUri("application/ld+json")
#     print(iana)
#     iana = vocabulary_providers.get("IANA").getUri("application/json")
#     print(iana)

#     europa = vocabulary_providers.get("DataEurope").getUri("JSON_LD")
#     print(europa)

