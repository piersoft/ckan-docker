01.06.2024 VERSIONE NON STABILE E CON MOLTI ERRORI: DA NON USARE IN PRODUZIONE. 

07.06.2024 AGGIORNATO FRONTEND DI CKAN CON HVD, ACCESS SERVICE E APPLICABLE LEGISLATION. 

18.06.2024 PRESENTI ANCORA ALCUNI BUG IN HARVESTING JSON. 

19.06.2024 SE SI VUOLE AVERE IL FILTRO HVD CATEGORY modificare in ckan.ini -> search.facets = organization groups tags res_format license_id hvd_category

20.06.2024 RISOLTO HARVESTING SIA IN RDF/TTL CHE CON DCAT JSON. ESEGUIRE 2 VOLTE L'HARVESTING PER ATTIVARE PATCH SUCCESSIVE SU FORMATI,ACCESS_RIGHTS ect

27.06.2024 La mappatura automatica dei GRUPPI durante gli harvesting, è settata manualmente nel file [mapping.py](https://github.com/piersoft/ckan-docker/blob/master/ckan/patches/ckanext-dcatapit/ckanext/dcatapit/mapping.py) (estensione DCATAPIT) e non in nella variabile ckanext.dcatapit.theme_group_mapping.file in ckan.ini. Punta a /srv/app/patches/theme_to_group.ini . Questo file viene copiato automaticamente in quella posizione, non bisogna fare nulla nella compilazione da Docker proposta. Se si fanno configurazioni differenti, va modificato il path.

**27.09.2024** Il codice è al 99,999% pronto per una installazione stand alone. le patch che ogni tanto aggiorno sono per harvesting di cataloghi remoti. Se non è il vostro caso, credo che si possa considerare stabile.

**09.04.2025** nel file [__euro_dcat_ap.py__](https://github.com/piersoft/ckan-docker/blob/master/ckan/patches/ckanext-dcat/ckanext/dcat/profiles/euro_dcat_ap.py) è inserita una patch delicata. l'accessURL viene sostituito con la landingpage della risorsa sul CKAN e il downloadURL viene popolato con il valore di download della risorsa (ex accessURL). Sostituire il path del dominio con il proprio portale CKAN:

	    if dataset_dict.get('id'):
               resource_dict['access_url']='https://www.piersoftckan.biz/dataset/'+dataset_dict['id']+'/resource/'+resource_dict['id']

Se NON si vuole tale trasformazione, commentare le due righe di codice precedenti. il downloadURL, in tal caso, verrà impostato identico all'accessURL
	       
**DATA.EUROPA.EU** richiede che le accessURL e i downloadURL siano raggiunbili in HEAD con risposta 200. Testare le proprie risorse con CURL -I URL 

Versione beta, stabile



# PREMESSA
Questa versione dockerizzata è a scopo dimostrativo. Non è una repository ufficiale. Le varie patch che in continuazione si stanno applicando, scaturiscono dall'analisi degli harvesting dei cataloghi nazionali, regionali e comunali, presenti su dati.gov.it. Ogni harvesting ha le sue peculiarietà e quindi necessita di avere patch nei file processors.py e presenti nella dir patches e profiles.py presente nell'estensione dcatapit customizzata che trovate inserita in questa repo, cosi come quella DCAT abilitata e patchata per i nuovi HVD.
Motivo per cui in questi files ci sono delle sostituzioni anche della radice delle url (www.piersoftckan.biz sostituito ad esempio con dati.toscana.it se holder_identifier è r_toscan).
Questo è dovuto al fatto che i cataloghi non sono tutti harvestabili nello stesso modo. Esempio dati.trentino.it viene harvestato correttamente tramite il catalog.rdf per cui tutti i metadati (se presenti e corretti) vengono rispecchiati nel catalogo che importa. Mentre i cataloghi che vengono harvestati tramite API (Toscana, Emilia, Marche, Basilicata) o non hanno proprio i metadati perchè hanno una versione molto datata di ckan (Marche e Basilicata) oppure vanno inserite delle configurazioni nelle sezioni di harvesting per imporre alcuni campi extra altrimenti non presenti (home page del catalog ect). Questo perchè il catalogo finale presente su www.piersoftckan.biz viene poi esportato in [__linked opendata__](https://www.piersoftckan.biz/sparql) e l'associazione corretta dei dataset/cataloghi/risorse è fondamentale. 
Perchè non si importa anche la Toscana o Emilia-Romagna con il catalog.rdf? perchè il loro portale da errore. Se digitate dati.emilia-romagna.it/catalog.ttl(o rdf) e poi magari a campione catalog.rdf?page=x vedrete che da errore. Se fossi il gestore del catalogo andrei a vedere i log. E' molto complicato "neutralizzare" gli errori nei cataloghi federati perchè non si è il proprietario della banca dati. Toscana importa ad esempio Firenze ma anche il Consorsio Lamma. Ci sono molti errori nei titoli, identificativi, tags ect e quindi le motivazioni per cui il catalog.ttl non viene generato possono essere molteplici. E' per questo che poi a sua volta, l'errore si propaga nel catalogo "centrale", in questo caso www.piersoftckan.biz. Ecco il motivo delle patch sui files su citati profiles, processors di dcat e profiles di dcatapit. si possono vedere quelle patch e magari replicarle nel catalogo locale. Consiglio di osservare anche il file rdf.py sempre nella cartella patches.


# Docker Compose setup for CKAN


* [Overview](#overview)
* [Installing Docker](#installing-docker)
* [docker compose vs docker-compose](#docker-compose-vs-docker-compose)
* [Install CKAN plus dependencies](#install-ckan-plus-dependencies)



## 1.  Overview

This is a set of configuration and setup files to run a CKAN site.

The CKAN images used are from the official CKAN [ckan-docker](https://github.com/ckan/ckan-docker-base) repo

The non-CKAN images are as follows:

* DataPusher: CKAN's [pre-configured DataPusher image](https://github.com/ckan/ckan-base/tree/main/datapusher).
* PostgreSQL: Official PostgreSQL image. Database files are stored in a named volume.
* Solr: CKAN's [pre-configured Solr image](https://github.com/ckan/ckan-solr). Index data is stored in a named volume.
* Redis: standard Redis image
* NGINX: latest stable nginx image that includes SSL and Non-SSL endpoints

The site is configured using environment variables that you can set in the `.env` file.

## 2.  Installing Docker

Install Docker by following the following instructions: [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

To verify a successful Docker installation, run `docker run hello-world` and `docker version`. These commands should output 
versions for client and server.

## 3.  docker compose *vs* docker-compose

All Docker Compose commands in this README will use the V2 version of Compose ie: `docker compose`. The older version (V1) 
used the `docker-compose` command. Please see [Docker Compose](https://docs.docker.com/compose/compose-v2/) for
more information.

## 4.  Install (build and run) CKAN plus dependencies

#### Base mode

Use this if you are a maintainer and will not be making code changes to CKAN or to CKAN extensions

Copy the included `.env.example` and rename it to `.env`. Modify it depending on your own needs.

ATTENTION!!! substitute every www.piersoftckan.biz in .env file (in example https://192.168.0.67:8443) and in each files into ckan/docker-entrypoint.d/ dir. Change in .env ckan_admin password..

Please note that when accessing CKAN directly (via a browser) ie: not going through NGINX you will need to make sure you have "ckan" set up
to be an alias to localhost in the local hosts file. Either that or you will need to change the `.env` entry for CKAN_SITE_URL

Using the default values on the `.env.example` file will get you a working CKAN instance. There is a sysadmin user created by default with the values defined in `CKAN_SYSADMIN_NAME` and `CKAN_SYSADMIN_PASSWORD`(`ckan_admin` and `test1234` by default). This should be obviously changed before running this setup as a public CKAN instance.


## First step: 

	git clone https://github.com/piersoft/ckan-docker.git

To build the images (remember before to rename and configure .env.example file) :

	docker compose build

To start the containers:

	docker compose up -d



**PS: if CKAN failed (unhealty) launch docker start ckan and after 2-3 minutes launch docker start nginx.**

**IMPORTANT AFTER CKAN IS RUNNING HEALTY (ONLY FIRST TIME):**

*Go to into docker:*

docker exec -it ckan bash 

cd /dockerentry-point 

sh 03.ckan_group.end

exit

docker restart ckan


This will start up the containers in the current window. By default the containers will log direct to this window with each container
using a different colour. 

At the end of the container start sequence there should be 6 containers running

![Screenshot 2022-12-12 at 10 36 21 am](https://user-images.githubusercontent.com/54408245/207012236-f9571baa-4d99-4ffe-bd93-30b11c4829e0.png)

After this step, CKAN should be running at `CKAN_SITE_URL`. (example https://192.168.0.67:8443 instead https://www.piersoftckan.biz)

For complete README, go to [__official repo__](https://github.com/ckan/ckan-docker)
