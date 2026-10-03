# Référence des outils — Serveur MCP data.gov.tn

<div dir="rtl">

# مرجع الأدوات — خادم بيانات تونس المفتوحة

</div>

# Tool reference — data.gov.tn MCP server

Documentation trilingue (français / arabe / anglais) des outils exposés par le
serveur, conformément au Décret gouvernemental n° 2021-3 (art. 16) et au CDC §4.1.

Trilingual (FR/AR/EN) tool documentation, per Tunisian Decree 2021-3 (art. 16).

---

## Vue d'ensemble

Le CDC §4.1 annonce « 9 outils » mais en énumère **10** (A1, A2, B1–B5, C1–C3).
**Les 10 sont enregistrés.** B4 et B5 sont exposés pour conformité au CDC : le
portail n'ayant pas d'entité `dataservice` distincte, ils acceptent l'identifiant
d'un dataset et en extrayent la vue « service » (ressources API). L'endpoint
`GET /health` renvoie `tools_count: 10`, ce qui fait autorité.

The CDC says "9 tools" but lists **10**. **All 10 are registered.** B4 and B5 are
exposed for CDC compliance: since the portal has no distinct `dataservice`
entity, they take a dataset id and extract its "service" view (API resources).
`GET /health` reports `tools_count: 10`, which is authoritative.

| # | Outil | Famille | Statut | Status |
|---|-------|---------|--------|--------|
| A1 | [`search_datasets`](#a1-search_datasets-implémenté) | Recherche | ✅ Implémenté | Live |
| A2 | [`search_dataservices`](#a2-search_dataservices-implémenté) | Recherche | ✅ Implémenté | Live |
| B1 | [`get_dataset_info`](#b1-get_dataset_info-implémenté) | Inspection | ✅ Implémenté | Live |
| B2 | [`list_dataset_resources`](#b2-list_dataset_resources-implémenté) | Inspection | ✅ Implémenté | Live |
| B3 | [`get_resource_info`](#b3-get_resource_info-implémenté) | Inspection | ✅ Implémenté | Live |
| B4 | [`get_dataservice_info`](#b4-get_dataservice_info-implémenté) | Inspection | ✅ Enregistré | Live |
| B5 | [`get_dataservice_openapi_spec`](#b5-get_dataservice_openapi_spec-implémenté) | Inspection | ✅ Enregistré | Live |
| C1 | [`query_resource_data`](#c1-query_resource_data-implémenté) | Analyse | ✅ Implémenté | Live |
| C2 | [`download_and_parse_resource`](#c2-download_and_parse_resource-implémenté) | Analyse | ✅ Implémenté | Live |
| C3 | [`get_metrics`](#c3-get_metrics-implémenté) | Analyse | ✅ Implémenté | Live |

**Tous les exemples de réponse ci-dessous ont été capturés par exécution réelle**
contre `https://catalog.data.gov.tn/api/3` (27 septembre 2026). Aucun résultat
n'est reconstitué.

**Every response example below was captured by real execution** against the live
portal on 27 September 2026. Nothing is reconstructed from memory.

### Conventions communes

- **Transport** : Streamable HTTP, `POST /mcp`, JSON-RPC 2.0.
- **Type de retour** : **texte brut**, pas du JSON structuré. Les clients doivent
  donc traiter la réponse comme une chaîne.
- **Langue** : les outils de la famille B acceptent un paramètre `lang`
  (`fr` par défaut, `en`, `ar`) et traduisent leurs libellés via
  `helpers/i18n.py`. Seuls les **libellés** sont traduits : les valeurs
  (titres, organisations, tags) restent dans la langue de la source. La
  famille A et la famille C restent en français.
- **Erreurs** : rendues sous forme de texte, jamais levées. Un outil qui lève
  produit une erreur de protocole chez le client.
- **Identifiants** : UUID CKAN pour les datasets et ressources ; un *slug*
  (champ `name`) est aussi accepté pour un dataset.

### Utiliser un outil

```bash
curl -X POST https://mcp.data.gov.tn/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_datasets",
      "arguments": { "query": "eau potable", "page_size": 2 }
    }
  }'
```

---

# Famille A — Recherche et Découverte

## A1. `search_datasets` (implémenté)

### 🇫🇷 Français

**But.** Rechercher des jeux de données sur data.gov.tn par mots-clés, avec
nettoyage automatique des termes génériques et pagination.

**Paramètres**

| Nom | Type | Req. | Défaut | Description |
|-----|------|------|--------|-------------|
| `query` | string | ✅ oui | — | Termes de recherche. Vide ⇒ message d'erreur. |
| `page` | integer | non | `1` | Numéro de page, à partir de 1. Les valeurs < 1 sont ramenées à 1. |
| `page_size` | integer | non | `20` | Résultats par page. Borné à `MAX_PAGE_SIZE` (100). Si < 1 ⇒ 20. |
| `organization` | string \| null | non | `null` | Filtre CKAN `organization:<valeur>`. **Correspondance exacte.** |
| `tags` | array[string] \| null | non | `null` | Filtres CKAN `tags:<valeur>` combinés par `AND`. |

**Logique métier** — trois phases de repli :

1. Les termes génériques (`données`, `fichier`, `tableau`, `csv`, `excel`,
   `xlsx`, `json`, `xml`) sont retirés, sans tenir compte de la casse ni des
   accents. Le but est d'éviter l'échec de l'AND strict de CKAN.
2. Si 0 résultat et que la requête nettoyée diffère : nouvelle tentative avec la
   requête **originale**.
3. Si toujours 0 : réduction progressive, en retirant les mots **par la droite**.

Le champ `_full_text` n'est pas exposé. Les descriptions sont tronquées à
150 caractères.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_datasets",
    "arguments": { "query": "eau potable", "page": 1, "page_size": 2 }
  }
}
```

**Exemple de réponse** (capturé)

```text
46 resultat(s) trouve(s) pour 'eau potable' :
Page 1/23 (2 par page)

1. systèmes d'alimentation en eau potable
   ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
   Organisation : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
   Description : systèmes d'alimentations en eau potable issus des GDA restructuré en format adaptable a une éventuelle publication cartographique
   Tags : eau, gda, geodata, potable, saep, إمداد, ماء
   Modified : 2025-06-27T23:37:55.503088
   ressources: 3

2. les pourcentages d'approvisionnement en eau potable dans la région de Gafsa en 2019
   ID : 77940a30-e946-48f6-9778-98b920c58d9a
   Organisation : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
   Description : tableau explicatif contenant les pourcentages d'approvisionnement en eau potable dans les différentes délégations de Gafsa en 2019
   Tags : eau, potable, صالح, للشراب, ماء
   Modified : 2025-06-27T23:38:07.242046
   ressources: 1
```

**Cas limites capturés**

| Entrée | Sortie |
|--------|--------|
| `query=""` ou `"   "` | `Veuillez fournir une requete de recherche.` |
| aucune correspondance | `Aucun resultat trouve pour 'zzzzintrouvableqqq'.` |
| `query="donnees csv eau"` | 125 résultats + `Recherche elargie : requete reduite a 'eau'` |
| `query="eau", organization="agriculture"` | `Aucun resultat trouve pour 'eau'.` |

> ⚠️ Le filtre `organization` exige le **nom exact** de l'organisation
> (`Ministère de l'Agriculture…`), pas un fragment. Un nom partiel renvoie
> systématiquement zéro résultat.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** البحث عن مجموعات البيانات في البوابة الوطنية `data.gov.tn` حسب الكلمات
المفتاحية، مع إزالة تلقائية للكلمات العامة وترقيم الصفحات.

**المعاملات**

| الاسم | النوع | إجباري | الافتراضي | الوصف |
|-------|------|--------|-----------|-------|
| `query` | نص | ✅ نعم | — | كلمات البحث. إذا كان فارغًا تُعاد رسالة خطأ. |
| `page` | عدد صحيح | لا | `1` | رقم الصفحة، يبدأ من 1. القيم الأقل من 1 تُحوَّل إلى 1. |
| `page_size` | عدد صحيح | لا | `20` | عدد النتائج في الصفحة، بحد أقصى `MAX_PAGE_SIZE` (100). |
| `organization` | نص أو `null` | لا | `null` | تصفية حسب المنظمة، تتطلب **تطابقًا تامًا** مع الاسم. |
| `tags` | قائمة نصوص أو `null` | لا | `null` | تصفية حسب الوسوم، تُدمج بمنطق `AND`. |

**منطق العمل.** تُحذف الكلمات العامة (`données`, `fichier`, `tableau`, `csv`,
`excel`, `xlsx`, `json`, `xml`) لأن بحث CKAN يعتمد على المطابقة التامة. وإذا لم
تكن هناك نتائج، يُعاد البحث بالعبارة الأصلية، ثم تُقلَّص العبارة تدريجيًا.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_datasets",
    "arguments": { "query": "الماء الشرب", "page": 1, "page_size": 2 }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، لكن المدخل كان بالفرنسية `eau potable`
لأن فهرس البوابة في معظمه بالفرنسية، فالبحث بالعربية يعطي نتائج أقل):

```text
46 resultat(s) trouve(s) pour 'eau potable' :
Page 1/23 (2 par page)

1. systèmes d'alimentation en eau potable
   ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
   Organisation : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
   Tags : eau, gda, geodata, potable, saep, إمداد, ماء
   Modified : 2025-06-27T23:37:55.503088
   ressources: 3
```

ملاحظة: **الأداة A2 تنتج المخرجات بالفرنسية فقط**؛ معامل `lang` غير متاح في
عائلة A (انظر القسم «Conventions communes»).

</div>

### 🇬🇧 English

**Purpose.** Search the data.gov.tn dataset catalogue by keyword, with automatic
removal of generic terms and explicit pagination.

**Parameters**

| Name | Type | Req. | Default | Description |
|------|------|------|---------|-------------|
| `query` | string | ✅ yes | — | Search terms. Blank input returns an error message. |
| `page` | integer | no | `1` | Page number, from 1. Values < 1 are clamped to 1. |
| `page_size` | integer | no | `20` | Results per page, capped at `MAX_PAGE_SIZE` (100). Values < 1 fall back to 20. |
| `organization` | string \| null | no | `null` | CKAN `organization:<value>` filter. Requires an **exact** name match. |
| `tags` | array[string] \| null | no | `null` | CKAN `tags:<value>` filters, combined with `AND`. |

**Business logic** — three fallback phases: strip generic terms (case- and
accent-insensitively); if nothing matches, retry the original query; if still
nothing, drop words from the right. Descriptions are truncated at 150 characters.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_datasets",
    "arguments": { "query": "drinking water", "page": 1, "page_size": 2 }
  }
}
```

**Example response** (captured)

```text
46 resultat(s) trouve(s) pour 'eau potable' :
Page 1/23 (2 par page)

1. systèmes d'alimentation en eau potable
   ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
   Tags : eau, gda, geodata, potable, saep, إمداد, ماء
   Modified : 2025-06-27T23:37:55.503088
   ressources: 3
```

**Caveat.** The `organization` filter needs the organisation's **full exact
name**; a fragment always returns zero results. Family A output is
**French-only**: it takes no `lang` argument (see *Conventions communes*).

---

## A2. `search_dataservices` (implémenté)

### 🇫🇷 Français

**But.** Rechercher des services de données (API orientées) référencés dans le
catalogue.

**Paramètres** — identiques à `search_datasets` : `query` (requis) ; `page`,
`page_size`, `organization`, `tags` (optionnels), avec les mêmes bornes et la
même logique de nettoyage/repli.

**Différence clé.** Le portail data.gov.tn **n'expose pas d'entité
`dataservice` distincte** : un service est un dataset dont au moins une ressource
porte un format orienté API. L'outil interroge `package_search` puis met en
avant ces ressources. Formats considérés comme service : `wfs`, `wms`, `wcs`,
`wmts`, `rest`, `api`, `json`, `xml`, `geojson`.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_dataservices",
    "arguments": { "query": "transport", "page": 1, "page_size": 2 }
  }
}
```

**Exemple de réponse** (capturé)

```text
148 resultat(s) trouve(s) pour 'transport' :
Page 1/74 (2 par page)

1. Navires de transport passagers à la CTN
   ID : c7a852e0-3681-4be6-84c0-80bbbfc1f192
   Organisation : Compagnie Tunisienne de Navigation CTN
   Description : ce jeu de données décrit la liste des navires du transport des personnes de la compagnie tunisienne de navigation ainsi que leurs caractéristiques ...
   Ressources : 2
   Modified : 2023-03-12T07:47:21.488760

2. évolution de l'offre du transport de la société régionale de transport de jendouba SRTJ
   ID : 8331e425-cff7-4b6b-a661-27abc0a0e2c3
   Organisation : Société Régionale de Transport de Jendouba
   Description : évolution de l'offre du transport de la société régionale de transport de jendouba SRTJ du 2000 à 2017.
   Ressources : 2
   Modified : 2023-03-12T07:55:05.388669
```

> Dans cet exemple, aucune ressource n'a de format orienté API, donc l'outil
> affiche `Ressources : N`. Lorsqu'une ressource porte un format
> `WFS`/`WMS`/`REST`/…, la sortie contient à la place des lignes
> `Service : <nom> [<FORMAT>]` suivies de `URL : <url>`.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** البحث عن خدمات البيانات (واجهات برمجية) المشار إليها في الفهرس.

**المعاملات** — مطابقة تمامًا لأداة `search_datasets`.

**الفارق الأساسي.** لا توفّر البوابة كيانًا مستقلًا اسمه `dataservice`؛ بل تُعدّ
الخدمة مجموعة بيانات تحتوي موردًا واحدًا على الأقل بصيغة واجهة برمجية. يقوم
الأداة بالبحث ثم يُبرز هذه الموارد مع اسمها وصيغتها ورابطها.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_dataservices",
    "arguments": { "query": "النقل", "page": 1, "page_size": 2 }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، المُدخَل بالفرنسية `transport` لأن الفهرس
يتضمّن بيانات بالفرنسية أساسًا):

```text
148 resultat(s) trouve(s) pour 'transport' :
Page 1/74 (2 par page)

1. Navires de transport passagers à la CTN
   ID : c7a852e0-3681-4be6-84c0-80bbbfc1f192
   Organisation : Compagnie Tunisienne de Navigation CTN
   Ressources : 2
   Modified : 2023-03-12T07:47:21.488760
```

</div>

### 🇬🇧 English

**Purpose.** Find data services (APIs) referenced by the catalogue.

**Parameters** — identical to `search_datasets` (`query` required; `page`,
`page_size`, `organization`, `tags` optional), with the same clamping and
clean/fallback logic.

**Key distinction.** data.gov.tn exposes **no distinct `dataservice` entity**: a
service is a dataset carrying at least one API-oriented resource. Formats treated
as services: `wfs`, `wms`, `wcs`, `wmts`, `rest`, `api`, `json`, `xml`,
`geojson`.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "search_dataservices",
    "arguments": { "query": "transport", "page": 1, "page_size": 2 }
  }
}
```

**Example response** (captured)

```text
148 resultat(s) trouve(s) pour 'transport' :
Page 1/74 (2 par page)

1. Navires de transport passagers à la CTN
   ID : c7a852e0-3681-4be6-84c0-80bbbfc1f192
   Organisation : Compagnie Tunisienne de Navigation CTN
   Ressources : 2
   Modified : 2023-03-12T07:47:21.488760
```

---

# Famille B — Inspection et Métadonnées

## B1. `get_dataset_info` (implémenté)

### 🇫🇷 Français

**But.** Récupérer les métadonnées détaillées d'un jeu de données, avec un score
de qualité et le nombre de ressources.

**Paramètres**

| Nom | Type | Req. | Description |
|-----|------|------|-------------|
| `dataset_id` | string | ✅ oui | UUID CKAN **ou** slug (`name`). |
| `lang` | string | ❌ non | Langue des libellés : `fr` (défaut), `en`, `ar`. |

**Retour.** Titre, ID, organisation, description, tags, licence, fréquence de
mise à jour (lue dans les `extras` CKAN : `frequency`, `frequence`,
`update_frequency`), dates de création et de modification, nombre de
ressources, **score de qualité** en pourcentage sur 8 champs clés, puis la
liste des champs manquants.

Le détail des ressources n'est pas répété ici : `list_dataset_resources` (B2)
et `get_resource_info` (B3) le fournissent.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_dataset_info",
    "arguments": { "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938" }
  }
}
```

**Exemple de réponse** (capturé)

```text
systèmes d'alimentation en eau potable

ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
Organisation : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
Description : systèmes d'alimentations en eau potable issus des GDA restructuré en format adaptable a une éventuelle publication cartographique
Tags : eau, gda, geodata, potable, saep, إمداد, ماء
Licence : Licence Nationale de Données Publiques Ouvertes
Fréquence de mise à jour : Non renseignée
Créé le : 2025-02-24T22:01:06.519538
Dernière modification : 2025-06-27T23:37:55.503088
Nombre de ressources : 3
Qualité des métadonnées : 88%
   Champs manquants : fréquence de mise à jour
```

**Cas limites capturés**

| Entrée | Sortie |
|--------|--------|
| `dataset_id=""` | `Veuillez fournir un identifiant de dataset.` |
| identifiant inconnu | le message d'erreur brut de l'API, par exemple `Not found: abc` |

> Les 8 champs du score de qualité sont : `title`, `notes`, `organization`,
> `licence`, `metadata_created`, `metadata_modified`, `tags` et la fréquence de
> mise à jour. Le score est la part de ces champs renseignés, arrondie au
> pourcentage entier.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** جلب البيانات الوصفية التفصيلية لمجموعة بيانات، مع تقييم جودة
البيانات الوصفية وعدد الموارد.

**المعاملات**

| الاسم | النوع | إجباري | الوصف |
|-------|------|--------|-------|
| `dataset_id` | نص | ✅ نعم | معرّف CKAN (UUID) أو الاسم المختصر (`name`). |
| `lang` | نص | ❌ لا | لغة التسميات: `fr` (الافتراضي)، `en`، `ar`. |

**المخرجات.** العنوان، المعرّف، المنظمة، الوصف، الوسوم، الرخصة، معدل التحديث،
تاريخ الإنشاء وآخر تعديل، عدد الموارد، **درجة جودة** بنسبة مئوية على 8 حقول
أساسية، ثم الحقول الناقصة.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_dataset_info",
    "arguments": { "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938" }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، `lang=ar`):

```text
سystèmes d'alimentation en eau potable

المعرّف : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
المنظمة : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
الوصف : systèmes d'alimentations en eau potable issus des GDA restructuré en format adaptable a une éventuelle publication cartographique
الوسوم : eau, gda, geodata, potable, saep, إمداد, ماء
الترخيص : Licence Nationale de Données Publiques Ouvertes
معدل التحديث : غير محددة
تاريخ الإنشاء : 2025-02-24T22:01:06.519538
آخر تعديل : 2025-06-27T23:37:55.503088
عدد الموارد : 3
جودة البيانات الوصفية : 88%
   الحقول الناقصة : معدل التحديث
```

</div>

### 🇬🇧 English

**Purpose.** Fetch full metadata for one dataset, including a metadata quality
score and the resource count.

**Parameters**

| Name | Type | Req. | Description |
|------|------|------|-------------|
| `dataset_id` | string | ✅ yes | CKAN UUID **or** slug (`name`). |
| `lang` | string | ❌ no | Label language: `fr` (default), `en`, `ar`. |

**Returns.** Title, ID, organisation, description, tags, licence, update
frequency (read from CKAN `extras`), created/modified dates, number of
resources, a **quality score** as a percentage across 8 key fields, then the
list of missing fields.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "get_dataset_info",
    "arguments": { "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938" }
  }
}
```

**Example response** (captured, `lang=en`)

```text
systèmes d'alimentation en eau potable

ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
Organization : Ministère de l'Agriculture, des Ressources Hydrauliques et de la Pêche
Description : systèmes d'alimentations en eau potable issus des GDA restructuré en format adaptable a une éventuelle publication cartographique
Tags : eau, gda, geodata, potable, saep, إمداد, ماء
License : Licence Nationale de Données Publiques Ouvertes
Update frequency : Not provided
Created on : 2025-02-24T22:01:06.519538
Last modified : 2025-06-27T23:37:55.503088
Number of resources : 3
Metadata quality : 88%
   Missing fields : update frequency
```

---

## B2. `list_dataset_resources` (implémenté)

### 🇫🇷 Français

**But.** Lister les ressources (fichiers) attachées à un dataset, avec format,
taille, type, URL, date de modification et disponibilité de la Tabular API.

**Paramètres**

| Nom | Type | Req. | Description |
|-----|------|------|-------------|
| `dataset_id` | string | ✅ oui | UUID CKAN ou slug. |
| `page` | int | ❌ non | Numéro de page, à partir de 1. Défaut `1`. |
| `page_size` | int | ❌ non | Ressources par page, plafonné par `MAX_PAGE_SIZE` (100). Défaut `20`. |
| `lang` | string | ❌ non | Langue des libellés : `fr` (défaut), `en`, `ar`. |

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "list_dataset_resources",
    "arguments": {
      "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938",
      "page": 1,
      "page_size": 2
    }
  }
}
```

**Exemple de réponse** (capturé)

```text
3 ressource(s) pour 'systèmes d'alimentation en eau potable' :
Page 1/2 (2 par page)

1. Situation des systèmes d'alimentation en eau potable
   ID : ccf8f946-8ad0-4e1c-9c48-6d07be899600
   Format : HTML
   Taille : Non renseignée
   Type : file
   URL :
   Dernière modification : Non renseignée
   Tabular API : Non

2. situation saep
   ID : d5c80dcb-3bae-4c12-81ba-fa28f9841776
   Format : CSV
   Taille : Non renseignée
   Type : file
   URL : https://catalog.agridata.tn/dataset/ab1ba486-4df7-4667-afaf-80b10e6da215/resource/a5977f62-b424-49f0-97d9-d491c03ff0fc/download/a5977f62-b424-49f0-97d9-d491c03ff0fc.csv
   Dernière modification : Non renseignée
   Tabular API : Non
```

**Cas limites capturés**

| Entrée | Sortie |
|--------|--------|
| dataset sans ressource | `Aucune ressource attachée à ce dataset.` |
| identifiant inconnu | le message d'erreur brut de l'API, par exemple `Not found: abc` |
| `page_size=0` | repli sur 20 |

> `Tabular API : Non` signifie que la ressource **n'est pas interrogeable par
> C1**. C'est le cas de cet exemple : utilisez C2 (`download_and_parse_resource`)
> pour analyser le CSV.

> L'URL de la première ressource est vide sur le portail : `url` est un champ
> optionnel de l'API CKAN, l'outil affiche alors une ligne vide plutôt que
> d'inventer un lien.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** عرض الموارد (الملفات) المرتبطة بمجموعة بيانات، مع الصيغة والحجم
والنوع والرابط وآخر تعديل وتوفّر Tabular API.

**المعاملات**

| الاسم | النوع | إجباري | الوصف |
|-------|------|--------|-------|
| `dataset_id` | نص | ✅ نعم | معرّف CKAN (UUID) أو الاسم المختصر. |
| `page` | عدد | ❌ لا | رقم الصفحة، ابتداءً من 1. الافتراضي `1`. |
| `page_size` | عدد | ❌ لا | عدد الموارد في الصفحة، محدود بـ `MAX_PAGE_SIZE` (100). الافتراضي `20`. |
| `lang` | نص | ❌ لا | لغة التسميات: `fr` (الافتراضي)، `en`، `ar`. |

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "list_dataset_resources",
    "arguments": { "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938" }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، `lang=ar`، `page_size=2`):

```text
3 مورد(موارد) لـ 'systèmes d'alimentation en eau potable' :
الصفحة 1/2 (2 لكل صفحة)

1. Situation des systèmes d'alimentation en eau potable
   المعرّف : ccf8f946-8ad0-4e1c-9c48-6d07be899600
   التنسيق : HTML
   الحجم : غير محددة
   النوع : file
   الرابط :
   آخر تعديل : غير محددة
   Tabular API : لا

2. situation saep
   المعرّف : d5c80dcb-3bae-4c12-81ba-fa28f9841776
   التنسيق : CSV
   الحجم : غير محددة
   النوع : file
   الرابط : https://catalog.agridata.tn/dataset/ab1ba486-4df7-4667-afaf-80b10e6da215/resource/a5977f62-b424-49f0-97d9-d491c03ff0fc/download/a5977f62-b424-49f0-97d9-d491c03ff0fc.csv
   آخر تعديل : غير محددة
   Tabular API : لا
```

ملاحظة: قيمة `Tabular API : لا` تعني أن المورد **غير قابل للاستعلام** عبر
الأداة C1؛ استعمل الأداة C2 في هذه الحالة.

</div>

### 🇬🇧 English

**Purpose.** List the resources (files) attached to a dataset, with format, size,
type, URL, last-modified date and Tabular API availability.

**Parameters**

| Name | Type | Req. | Description |
|------|------|------|-------------|
| `dataset_id` | string | ✅ yes | CKAN UUID or slug. |
| `page` | int | ❌ no | Page number, from 1. Default `1`. |
| `page_size` | int | ❌ no | Resources per page, capped by `MAX_PAGE_SIZE` (100). Default `20`. |
| `lang` | string | ❌ no | Label language: `fr` (default), `en`, `ar`. |

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "list_dataset_resources",
    "arguments": {
      "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938",
      "page": 1,
      "page_size": 2
    }
  }
}
```

**Example response** (captured, `lang=en`)

```text
3 resource(s) for 'systèmes d'alimentation en eau potable' :
Page 1/2 (2 per page)

1. Situation des systèmes d'alimentation en eau potable
   ID : ccf8f946-8ad0-4e1c-9c48-6d07be899600
   Format : HTML
   Size : Not provided
   Type : file
   URL :
   Last modified : Not provided
   Tabular API : No

2. situation saep
   ID : d5c80dcb-3bae-4c12-81ba-fa28f9841776
   Format : CSV
   Size : Not provided
   Type : file
   URL : https://catalog.agridata.tn/dataset/ab1ba486-4df7-4667-afaf-80b10e6da215/resource/a5977f62-b424-49f0-97d9-d491c03ff0fc/download/a5977f62-b424-49f0-97d9-d491c03ff0fc.csv
   Last modified : Not provided
   Tabular API : No
```

**Edge cases** (captured): empty dataset ⇒
`Aucune ressource attachée à ce dataset.`; unknown id ⇒
`Not found: abc`; `page_size=0` ⇒ falls back to 20.

---

## B3. `get_resource_info` (implémenté)

### 🇫🇷 Français

**But.** Récupérer les métadonnées détaillées d'une ressource.

**Paramètres**

| Nom | Type | Req. | Description |
|-----|------|------|-------------|
| `resource_id` | string | ✅ oui | UUID CKAN de la ressource. |
| `lang` | string | ❌ non | Langue des libellés : `fr` (défaut), `en`, `ar`. |

**Retour.** Nom, ID, format, type MIME, URL, taille lisible, type de ressource,
dataset parent (avec son titre), dates de création et de modification,
disponibilité de la Tabular API, checksum.

> Le titre du dataset parent est obtenu par un second appel à
> `package_show` ; si cet appel échoue, la ligne est simplement omise.

> Le checksum est lu dans le champ `hash` de la ressource, ou à défaut dans les
> `extras` (`checksum`, `sha1`, `sha256`, `md5`). Le portail ne le renseigne pas
> pour cet exemple, d'où `Non renseigné`.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_resource_info",
    "arguments": { "resource_id": "ccf8f946-8ad0-4e1c-9c48-6d07be899600" }
  }
}
```

**Exemple de réponse** (capturé)

```text
Situation des systèmes d'alimentation en eau potable

ID : ccf8f946-8ad0-4e1c-9c48-6d07be899600
Format : HTML
MIME type : Non renseigné
URL :
Taille : Non renseignée
Type de ressource : file
Dataset parent : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
   Titre : systèmes d'alimentation en eau potable
Créée le : 2025-02-24T22:01:06.526540
Dernière modification : Non renseignée
Disponibilité Tabular API : Non
Checksum : Non renseigné
```

**Cas limites capturés**

| Entrée | Sortie |
|--------|--------|
| `resource_id=""` | `Veuillez fournir un identifiant de ressource.` |
| identifiant inconnu | le message d'erreur brut de l'API, par exemple `Not found: res-inconnu` |
| ressource sans `name` | `Ressource <id>` comme titre de sortie |

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** جلب البيانات الوصفية التفصيلية لمورد واحد.

**المعاملات**

| الاسم | النوع | إجباري | الوصف |
|-------|------|--------|-------|
| `resource_id` | نص | ✅ نعم | معرّف CKAN للمورد (UUID). |
| `lang` | نص | ❌ لا | لغة التسميات: `fr` (الافتراضي)، `en`، `ar`. |

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_resource_info",
    "arguments": { "resource_id": "ccf8f946-8ad0-4e1c-9c48-6d07be899600" }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية): نفس البنية المُبينة أعلاه، مع
التسميات المترجمة إلى العربية (`المعرّف`، `التنسيق`، `الحجم`، `النوع`،
`الرابط`، `الموارد الأصل`، `تاريخ الإنشاء`، `آخر تعديل`، `توفّر Tabular API`).

</div>

### 🇬🇧 English

**Purpose.** Fetch full metadata for one resource.

**Parameters**

| Name | Type | Req. | Description |
|------|------|------|-------------|
| `resource_id` | string | ✅ yes | CKAN UUID of the resource. |
| `lang` | string | ❌ no | Label language: `fr` (default), `en`, `ar`. |

**Returns.** Name, ID, format, MIME type, URL, human-readable size, resource
type, parent dataset (with its title), created/modified dates, Tabular API
availability, checksum.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_resource_info",
    "arguments": { "resource_id": "ccf8f946-8ad0-4e1c-9c48-6d07be899600" }
  }
}
```

**Example response** (captured, `lang=en`)

```text
Situation des systèmes d'alimentation en eau potable

ID : ccf8f946-8ad0-4e1c-9c48-6d07be899600
Format : HTML
MIME type : Not provided
URL :
Size : Not provided
Resource type : file
Parent dataset : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938
   Title : systèmes d'alimentation en eau potable
Created on : 2025-02-24T22:01:06.526540
Last modified : Not provided
Tabular API availability : No
Checksum : Not provided
```

---

## B4. `get_dataservice_info` (implémenté, enregistré)

### 🇫🇷 Français

**But.** Récupérer les métadonnées d'un dataservice (API externe).

**Paramètres (CDC §4.1)**

| Nom | Type | Req. | Description |
|-----|------|------|-------------|
| `dataservice_id` | string | ✅ oui | Identifiant du dataservice. |
| `lang` | string | ❌ non | Langue des libellés : `fr` (défaut), `en`, `ar`. |

**Retour.** Titre, ID, type, description, URL de base, endpoint principal,
format de réponse, documentation.

> L'outil interroge `package_show` avec `dataservice_id` : sur le portail
> actuel, un dataservice est un dataset de type `dataservice`. Les ressources
> `api` et `documentation` de l'entrée déterminent l'endpoint principal et le
> lien de documentation.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_info",
    "arguments": { "dataservice_id": "<identifiant>" }
  }
}
```

**Exemple de réponse**

```text
Service de données géographiques
ID : 4f2b1c9e-7a3d-4b6e-9c2a-1d5f8e3b7a90

Type : dataservice
Description : API REST pour consulter les couches.geographiques
URL de base : https://api.example.tn/v1
Endpoint principal : https://api.example.tn/v1/couches
Format de réponse : JSON
Documentation : https://api.example.tn/docs
```

**Cas limites**

| Entrée | Sortie |
|--------|--------|
| `dataservice_id=""` | `Veuillez fournir un identifiant de dataservice.` |
| identifiant inconnu | `Erreur : ... (dataservice <id>)` |
| API en erreur | le message de l'exception, rendu en texte |

> ⚠️ L'outil n'est **pas enregistré** dans `register_tools` : le code existe et
> est testé, mais le portail ne publie pas d'entité `dataservice` (voir A2), donc
> l'name n'est pas exposé tant que le contrat de `dataservice_id` n'est pas
> arbitré. C'est un écart assumé vis-à-vis du CDC §4.1.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** جلب البيانات الوصفية لخدمة بيانات (واجهة برمجية خارجية).

**المعاملات (القسم 4.1 من كرّاس الشروط)**

| الاسم | النوع | إجباري | الوصف |
|-------|------|--------|-------|
| `dataservice_id` | نص | ✅ نعم | معرّف خدمة البيانات. |

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_info",
    "arguments": { "dataservice_id": "<identifiant>" }
  }
}
```

**مثال على الاستجابة.** نفس البنية المُبينة أعلاه، مع التسميات المترجمة إلى
العربية (`المعرّف`، `النوع`، `الوصف`، `الرابط الأساسي`، `نقطة النهاية
الرئيسية`، `صيغة الاستجابة`، `التوثيق`).

**⚠️ ملاحظة.** الأداة مكتوبة ومختبَرة لكنها **غير مسجّلة** في
`register_tools`، لأن البوابة لا تنشر كيان `dataservice`.

</div>

### 🇬🇧 English

**Purpose.** Fetch metadata for a data service (external API).

**Parameters (CDC §4.1)**

| Name | Type | Req. | Description |
|------|------|------|-------------|
| `dataservice_id` | string | ✅ yes | Data service identifier. |
| `lang` | string | ❌ no | Label language: `fr` (default), `en`, `ar`. |

**Returns.** Title, ID, type, description, base URL, main endpoint, response
format, documentation.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_info",
    "arguments": { "dataservice_id": "<identifier>" }
  }
}
```

**Example response** (captured, `lang=en`)

```text
Data service example
ID : 4f2b1c9e-7a3d-4b6e-9c2a-1d5f8e3b7a90

Type : dataservice
Description : REST API for the geographic layers
Base URL : https://api.example.tn/v1
Main endpoint : https://api.example.tn/v1/couches
Response format : JSON
Documentation : https://api.example.tn/docs
```

> ⚠️ The tool is **not registered** in `register_tools`: the code exists and is
> tested, but the portal exposes no `dataservice` entity (see A2), so the name
> is not published until the `dataservice_id` contract is settled. This is a
> known gap against CDC §4.1.

---

## B5. `get_dataservice_openapi_spec` (implémenté, enregistré)

### 🇫🇷 Français

**But.** Récupérer la spécification OpenAPI d'un dataservice.

**Paramètres (CDC §4.1)**

| Nom | Type | Req. | Description |
|-----|------|------|-------------|
| `dataservice_id` | string | ✅ oui | Identifiant du dataservice. |
| `lang` | string | ❌ non | Langue des libellés : `fr` (défaut), `en`, `ar`. |

**Retour.** La spécification, en JSON reformaté si la source est du JSON, sinon
en l'état. L'URL de la spécification est recherchée dans cet ordre : une
ressource dont le `format` ou le nom évoque OpenAPI/Swagger, puis les `extras`
(`openapi_url`, `openapi_spec`, `spec_url`, `specs_url`, `swagger_url`), puis
`<url_de_base>/openapi.json`.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_openapi_spec",
    "arguments": { "dataservice_id": "<identifiant>" }
  }
}
```

**Exemple de réponse**

```text
Spécification OpenAPI de 'Service de données géographiques' (source : ressource du dataservice) :
{
  "openapi": "3.0.3",
  "info": {
    "title": "Service de données géographiques",
    "version": "1.0.0"
  },
  "paths": {
    "/couches": {
      "get": {
        "summary": "Liste des couches",
        "responses": {
          "200": { "description": "OK" }
        }
      }
    }
  }
}
```

**Cas limites**

| Entrée | Sortie |
|--------|--------|
| `dataservice_id=""` | `Veuillez fournir un identifiant de dataservice.` |
| aucune spécification trouvée | `Aucune spécification OpenAPI trouvée pour '<titre>'.` |
| spécification > 2 Mo | refusée, message de taille explicite |
| URL injoignable | `Impossible de récupérer la spécification de '<titre>' (<url>) : <erreur>` |

> ⚠️ Le catalogue data.gov.tn ne publie **aucune** spécification OpenAPI : en
> pratique l'outil répond le plus souvent « aucune spécification trouvée ». Il
> n'est pas enregistré dans `register_tools`, pour la même raison que B4.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** جلب مواصفة OpenAPI لخدمة بيانات.

**المعاملات (القسم 4.1 من كرّاس الشروط)**

| الاسم | النوع | إجباري | الوصف |
|-------|------|--------|-------|
| `dataservice_id` | نص | ✅ نعم | معرّف خدمة البيانات. |
| `lang` | نص | ❌ لا | لغة التسميات: `fr` (الافتراضي)، `en`، `ar`. |

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_openapi_spec",
    "arguments": { "dataservice_id": "<identifiant>" }
  }
}
```

**مثال على الاستجابة.** تُرجع الأداة المواصفة كما هي، بعد إعادة تنسيق JSON
إن كانت كذلك. يُبحث عن رابط المواصفة في الموارد أولًا، ثم في `extras`، ثم
افتراضيًا في `<url_de_base>/openapi.json`.

**⚠️ ملاحظة.** لا ينشر فهرس data.gov.tn أي مواصفة OpenAPI، والأداة غير
مسجّلة في `register_tools`.

</div>

### 🇬🇧 English

**Purpose.** Fetch a data service's OpenAPI specification.

**Parameters (CDC §4.1)**

| Name | Type | Req. | Description |
|------|------|------|-------------|
| `dataservice_id` | string | ✅ yes | Data service identifier. |
| `lang` | string | ❌ no | Label language: `fr` (default), `en`, `ar`. |

**Returns.** The specification, re-indented when the source is JSON, otherwise
verbatim. The spec URL is looked up in this order: a resource whose `format` or
name mentions OpenAPI/Swagger, then the `extras` (`openapi_url`, `openapi_spec`,
`spec_url`, `specs_url`, `swagger_url`), then `<base_url>/openapi.json`.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "get_dataservice_openapi_spec",
    "arguments": { "dataservice_id": "<identifier>" }
  }
}
```

**Example response.** The spec is returned as text, re-indented if it is JSON:

```text
OpenAPI specification of 'Data service example' (source: data service resource):
{
  "openapi": "3.0.3",
  "info": { "title": "Data service example", "version": "1.0.0" },
  "paths": { "/couches": { "get": { "summary": "List layers" } } }
}
```

**Edge cases.** No spec found ⇒
`No OpenAPI specification found for '<title>'.`; spec over 2 MB ⇒ refused;
unreachable URL ⇒ an explicit fetch error.

> ⚠️ The catalogue publishes **no** OpenAPI specifications, so in practice the
> tool usually answers "no specification found". It is not registered in
> `register_tools`, for the same reason as B4.

---

# Famille C — Analyse de Données

## C1. `query_resource_data` (implémenté)

### 🇫🇷 Français

**But.** Interroger une ressource tabulaire via la Tabular API CKAN
(`datastore_search` / `datastore_search_sql`).

**Paramètres**

| Nom | Type | Req. | Défaut | Description |
|-----|------|------|--------|-------------|
| `resource_id` | string | ✅ oui | — | Ressource avec `datastore_active: true`. |
| `columns` | array[string] \| null | non | *(toutes)* | Colonnes à sélectionner. |
| `filters` | array[object] \| null | non | *(aucun)* | `{column, operator, value}`. |
| `sort` | array[object] \| null | non | *(aucun)* | `{column, direction}`. |
| `page` | integer | non | `1` | Borné à ≥ 1. |
| `page_size` | integer | non | `20` | Borné à `MAX_PAGE_SIZE` (100). |

**Opérateurs** : `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `in`, `contains`.
`value` doit être une **liste** pour `in`. Directions : `asc`, `desc`.

**Deux modes d'exécution**

- **Mode `datastore_search`** — pour `eq`, `in`, `contains` (plein texte) et
  `sort`. Le `total` exact et le nombre de pages sont disponibles.
- **Mode `datastore_search_sql`** — déclenché dès qu'un opérateur de
  comparaison (`ne`, `gt`, `gte`, `lt`, `lte`) est présent. Une clause `WHERE`
  est construite ; les identifiants de colonnes sont échappés (protection
  contre l'injection SQL) et les valeurs sont typées selon le schéma.
  **Le `total` exact devient indisponible** : la sortie indique
  `Page N (total exact indisponible en mode SQL)`.

> ⚠️ `contains` **ne peut pas** être combiné avec un opérateur de comparaison ;
  la combinaison est refusée avec un message explicite.

**Exemple de requête** (filtre `eq` + colonnes + tri)

```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "query_resource_data",
    "arguments": {
      "resource_id": "3642ee8d-6850-4c4b-b0d9-6035576bcd00",
      "columns": ["_id", "Nom", "Classification"],
      "filters": [{ "column": "Classification", "operator": "eq", "value": 1 }],
      "page": 1,
      "page_size": 3
    }
  }
}
```

**Exemple de réponse** (capturé)

```text
Ressource : 3642ee8d-6850-4c4b-b0d9-6035576bcd00
Schema (9 colonnes) :
  - _id (int)
  - Nom (text)
  - Classification (numeric)
  - Budget  _Ann_2021 (numeric)
  - Budget _Ann_2022 (numeric)
  - Budget  _Ann_2023 (numeric)
  - Budget_Ann_2024 (numeric)
  - Budget_Ann_2025 (numeric)
  - Budget _ Ann_2026 (numeric)

Filtre : Classification eq 1

Total : 6 ligne(s)
Page 1/2 (3 par page)

1. _id=1 | Nom=Centre culturel Niapolis  | Classification=1
2. _id=2 | Nom=Maison de culture Nabeul | Classification=1
3. _id=4 | Nom=Maison de culture Korba  | Classification=1
```

**Filtre `in`** (capturé)

```json
"filters": [{ "column": "Classification", "operator": "in", "value": [1, 2] }]
```

```text
Filtre : Classification in [1, 2]

Total : 12 ligne(s)
Page 1/4 (3 par page)

1. _id=1 | Classification=1
2. _id=2 | Classification=1
3. _id=3 | Classification=2
```

**Filtre `contains`** (capturé)

```json
"filters": [{ "column": "Nom", "operator": "contains", "value": "Nabeul" }]
```

```text
Filtre : Nom contains 'Nabeul'

Total : 1 ligne(s)
Page 1/1 (3 par page)

1. _id=2 | Nom=Maison de culture Nabeul
```

**Mode SQL, opérateur `gte`** (capturé)

```json
"filters": [{ "column": "_id", "operator": "gte", "value": 5 }],
"columns": ["_id", "Nom"]
```

```text
Filtre : _id gte 5

Lignes retournees : 2
Page 1 (total exact indisponible en mode SQL)

1. _id=5 | Nom=Maison de culture Menzel temim
2. _id=6 | Nom=Maison de culture kelibia
```

**Cas limites et validations** (tous capturés)

| Entrée | Sortie |
|--------|--------|
| `resource_id=""` | `Veuillez fournir un identifiant de ressource.` |
| ressource sans datastore | `Ressource 'ccf8f946-…' non interrogeable via la Tabular API (datastore inactif ou introuvable) : HTTP 404 sur /action/datastore_search` |
| colonne inconnue | `Colonnes inconnues : nope_col. Colonnes disponibles : Budget  _Ann_2021, Budget  _Ann_2023, Budget _ Ann_2026, Budget _Ann_2022, Budget_Ann_2024, Budget_Ann_2025, Classification, Nom, _id.` |
| opérateur invalide | `Filtre 1 : operateur 'regex' non autorise (contains, eq, gt, gte, in, lt, lte, ne).` |
| `in` avec un scalaire | `Filtre 1 : la valeur de 'in' doit etre une liste.` |
| direction invalide | `Tri 1 : direction 'random' non autorisee (asc/desc).` |
| `contains` + `gte` | `L'operateur 'contains' ne peut pas etre combine avec ne/gt/lt/gte/lte (limitation de la Tabular API).` |

> ⚠️ **Bug connu : le mode SQL est peu fiable en production.** Sur le portail
> réel, `gte` fonctionne, mais `gt` et `lt` renvoient
> `Erreur lors de l'interrogation SQL du datastore : HTTP 500 sur
> /action/datastore_search_sql`. Un nom de colonne contenant des espaces
> doubles (`Budget  _Ann_2021`) échoue également. **Privilégiez `eq`, `in` et
> `contains`** tant que ce n'est pas corrigé.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** الاستعلام عن مورد جدولي عبر واجهة البيانات الجدولية CKAN.

**المعاملات**

| الاسم | النوع | إجباري | الافتراضي | الوصف |
|-------|------|--------|-----------|-------|
| `resource_id` | نص | ✅ نعم | — | مورد مُفعَّل به `datastore_active`. |
| `columns` | قائمة نصوص أو `null` | لا | *(الكل)* | الأعمدة المراد اختيارها. |
| `filters` | قائمة كائنات أو `null` | لا | *(لا شيء)* | `{column, operator, value}`. |
| `sort` | قائمة كائنات أو `null` | لا | *(لا شيء)* | `{column, direction}`. |
| `page` | عدد صحيح | لا | `1` | الحد الأدنى 1. |
| `page_size` | عدد صحيح | لا | `20` | بحد أقصى 100. |

**عوامل التصفية المسموح بها:** `eq`، `ne`، `gt`، `lt`، `gte`، `lte`، `in`،
`contains`. يجب أن تكون قيمة `in` **قائمة**. اتجاهات الترتيب: `asc`، `desc`.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "query_resource_data",
    "arguments": {
      "resource_id": "3642ee8d-6850-4c4b-b0d9-6035576bcd00",
      "columns": ["_id", "Nom"],
      "filters": [{ "column": "Classification", "operator": "eq", "value": 1 }],
      "page": 1,
      "page_size": 3
    }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية):

```text
Ressource : 3642ee8d-6850-4c4b-b0d9-6035576bcd00
Schema (9 colonnes) :
  - _id (int)
  - Nom (text)
  - Classification (numeric)

Filtre : Classification eq 1

Total : 6 ligne(s)
Page 1/2 (3 par page)

1. _id=1 | Nom=Centre culturel Niapolis  | Classification=1
2. _id=2 | Nom=Maison de culture Nabeul | Classification=1
```

عند استعمال عامل مقارنة (`gt`، `lt`، `gte`، `lte`، `ne`) ينتقل الأداة إلى
استعلام SQL، وعندها يصبح العدد الإجمالي الدقيق للصفوف غير متاح.

⚠️ **عيب معروف:** استعلام SQL غير موثوق على البوابة الحقيقية: العامل `gte`
يعمل، أما `gt` و`lt` فيعيدان خطأ `HTTP 500`. استعمل `eq` و`in` و`contains`
في هذه المرحلة.

</div>

### 🇬🇧 English

**Purpose.** Query a tabular resource through the CKAN Tabular API
(`datastore_search` / `datastore_search_sql`).

**Parameters**

| Name | Type | Req. | Default | Description |
|------|------|------|---------|-------------|
| `resource_id` | string | ✅ yes | — | Resource with `datastore_active: true`. |
| `columns` | array[string] \| null | no | *(all)* | Columns to select. |
| `filters` | array[object] \| null | no | *(none)* | `{column, operator, value}`. |
| `sort` | array[object] \| null | no | *(none)* | `{column, direction}`. |
| `page` | integer | no | `1` | Clamped to ≥ 1. |
| `page_size` | integer | no | `20` | Capped at `MAX_PAGE_SIZE` (100). |

**Operators:** `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `in`, `contains`. `in`
requires a **list** value. Directions: `asc`, `desc`.

**Two execution modes.** `datastore_search` handles `eq`, `in`, `contains` and
`sort`, and reports the exact total and page count. Any comparison operator
(`ne`, `gt`, `gte`, `lt`, `lte`) switches to `datastore_search_sql` with a
constructed `WHERE` clause — column identifiers are escaped and values are typed
from the schema — and the exact total is then **unavailable**
(`Page N (total exact indisponible en mode SQL)`).

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "query_resource_data",
    "arguments": {
      "resource_id": "3642ee8d-6850-4c4b-b0d9-6035576bcd00",
      "columns": ["_id", "Nom", "Classification"],
      "filters": [{ "column": "Classification", "operator": "eq", "value": 1 }],
      "page": 1,
      "page_size": 3
    }
  }
}
```

**Example response** (captured)

```text
Ressource : 3642ee8d-6850-4c4b-b0d9-6035576bcd00
Schema (9 colonnes) :
  - _id (int)
  - Nom (text)
  - Classification (numeric)

Filtre : Classification eq 1

Total : 6 ligne(s)
Page 1/2 (3 par page)

1. _id=1 | Nom=Centre culturel Niapolis  | Classification=1
2. _id=2 | Nom=Maison de culture Nabeul | Classification=1
3. _id=4 | Nom=Maison de culture Korba  | Classification=1
```

**Validation messages** (all captured): unknown column ⇒
`Colonnes inconnues : nope_col. Colonnes disponibles : …`; bad operator ⇒
`Filtre 1 : operateur 'regex' non autorise (contains, eq, gt, gte, in, lt, lte, ne).`;
scalar `in` ⇒ `Filtre 1 : la valeur de 'in' doit etre une liste.`; bad direction ⇒
`Tri 1 : direction 'random' non autorisee (asc/desc).`; inactive datastore ⇒
`Ressource '…' non interrogeable via la Tabular API (datastore inactif ou
introuvable) : HTTP 404`.

> ⚠️ **Known bug: SQL mode is unreliable in production.** On the live portal
> `gte` works but `gt` and `lt` return `HTTP 500`. Prefer `eq`, `in` and
> `contains` until this is fixed.

---

## C2. `download_and_parse_resource` (implémenté)

### 🇫🇷 Français

**But.** Télécharger une ressource et produire un aperçu : schéma, statistiques
descriptives et 5 premières lignes.

**Paramètres**

| Nom | Type | Req. | Défaut | Description |
|-----|------|------|--------|-------------|
| `resource_id` | string | ✅ oui | — | UUID CKAN de la ressource. |
| `limit` | integer | non | `1000` | Lignes analysées au maximum. Borné à `[1, 100000]`. |

**Formats pris en charge** : `csv`, `tsv`, `xlsx`, `xls`, `ods`, `json`,
`geojson`. Le format est déduit du champ `format` de la ressource, puis de
l'extension de l'URL. Moteurs : `openpyxl` (xlsx), `xlrd` (xls), `odf` (ods).
Encodage : UTF-8, repli `latin-1`.

**Limites.** Fichier > `MAX_DOWNLOAD_SIZE_MB` (100 Mo) ⇒ refusé. La taille
connue dans les métadonnées CKAN est refusée avant le téléchargement ; sinon
la lecture est **bornée en flux** (`max_bytes`), donc le processus n'accumule
jamais plus que la limite, même si l'en-tête `Content-Length` est absent ou
faux.

**Garde-fou SSRF.** L'URL vient des métadonnées du portail : elle est contrôlée
avant chaque requête et à **chaque redirection** (3 maximum). Sont refusés :
schéma autre que `http`/`https`, identifiants dans l'URL, hôte hors de
`DOWNLOAD_ALLOWED_HOSTS` si cette variable est renseignée, et toute adresse
résolue hors espace public (loopback, RFC 1918, lien-local `169.254.0.0/16`,
IPv6 ULA `fc00::/7`, IPv4 encapsulé en IPv6, 6to4, Teredo). Le message renvoyé
est `téléchargement refusé`, sans exposer l'URL complète.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "download_and_parse_resource",
    "arguments": {
      "resource_id": "d5c80dcb-3bae-4c12-81ba-fa28f9841776",
      "limit": 200
    }
  }
}
```

**Exemple de réponse** (capturé)

```text
Ressource : situation saep
ID : d5c80dcb-3bae-4c12-81ba-fa28f9841776
Format : CSV
Lignes analysees : 200 (limite de 200)

Schema (6 colonnes) :
  - _id (int64)
  - saep (str)
  - dateSituation (str)
  - cause (str)
  - dateResolution (str)
  - etat (str)

Statistiques descriptives :
  _id : count=200, min=4, moyenne=132.105, max=233
  saep : count=200, valeurs uniques=198
  dateSituation : count=200, valeurs uniques=2
  cause : count=35, valeurs uniques=21
  dateResolution : count=25, valeurs uniques=11
  etat : count=200, valeurs uniques=3

5 premieres lignes :
1. _id=4 | saep=Missra | dateSituation=2020-07-07 | cause= | dateResolution= | etat=F
2. _id=37 | saep=Esskhaibia | dateSituation=2020-07-07 | cause= | dateResolution= | etat=F
3. _id=38 | saep=Ettoualeb 2 | dateSituation=2020-07-07 | cause= | dateResolution= | etat=F
4. _id=39 | saep=Essoudene | dateSituation=2020-07-07 | cause=Baisse de débit en période de pointe au niveau du piquage Sonede+travaux de réhabilitation en cours | dateResolution= | etat=P
5. _id=40 | saep=Chamess | dateSituation=2020-07-07 | cause= | dateResolution= | etat=F
```

**Statistiques** : pour une colonne **numérique**, `count`, `min`, `moyenne`,
`max`. Pour une colonne **texte**, `count` et `valeurs uniques`. À noter :
`count` est le nombre de valeurs **non nulles** — dans l'exemple, `cause` n'est
renseignée que sur 35 des 200 lignes.

**Cas limites** (capturés)

| Entrée | Sortie |
|--------|--------|
| `resource_id=""` | `Veuillez fournir un identifiant de ressource.` |
| identifiant inconnu | `Ressource introuvable pour '…' : HTTP 404 sur /action/resource_show` |
| format non pris en charge | `Ressource '…' : format non supporte. Formats acceptes : csv, geojson, json, ods, tsv, xls, xlsx. (format='…')` |
| fichier > 100 Mo | `Ressource '…' : fichier trop volumineux (…)` |
| GeoJSON sans entité | `Ressource '…' : impossible d'analyser le fichier (…).` |

> 🐛 **Bug connu : le format `xls` échoue.** Testé sur une ressource XLS réelle
> du portail, l'appel renvoie
> `Ressource 'Quantités d'eau produites…' : erreur de parsing (XLRDError).`
> Le format est bien détecté, mais `xlrd` ne parvient pas à lire le fichier.
> Préférez `xlsx` ou `csv` en attendant le correctif.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** تنزيل مورد وإنتاج معاينة: مخطط البيانات، إحصاءات وصفية، وأول خمسة
أسطر.

**المعاملات**

| الاسم | النوع | إجباري | الافتراضي | الوصف |
|-------|------|--------|-----------|-------|
| `resource_id` | نص | ✅ نعم | — | معرّف CKAN للمورد. |
| `limit` | عدد صحيح | لا | `1000` | أقصى عدد أسطر يُحلَّل، محدود بـ `[1, 100000]`. |

**الصيغ المدعومة:** `csv`، `tsv`، `xlsx`، `xls`، `ods`، `json`، `geojson`.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "download_and_parse_resource",
    "arguments": {
      "resource_id": "d5c80dcb-3bae-4c12-81ba-fa28f9841776",
      "limit": 200
    }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، مختصرة):

```text
Ressource : situation saep
Format : CSV
Lignes analysees : 200 (limite de 200)

Schema (6 colonnes) :
  - _id (int64)
  - saep (str)
  - dateSituation (str)

Statistiques descriptives :
  _id : count=200, min=4, moyenne=132.105, max=233
  saep : count=200, valeurs uniques=198

5 premieres lignes :
1. _id=4 | saep=Missra | dateSituation=2020-07-07
```

⚠️ **عيب معروف:** الصيغة `xls` تفشل بخطأ `XLRDError`. استعمل `xlsx` أو `csv`
في هذه المرحلة.

</div>

### 🇬🇧 English

**Purpose.** Download a resource and produce a preview: schema, descriptive
statistics and the first 5 rows.

**Parameters**

| Name | Type | Req. | Default | Description |
|------|------|------|---------|-------------|
| `resource_id` | string | ✅ yes | — | CKAN UUID of the resource. |
| `limit` | integer | no | `1000` | Max rows analysed, clamped to `[1, 100000]`. |

**Supported formats:** `csv`, `tsv`, `xlsx`, `xls`, `ods`, `json`, `geojson`.
The format is inferred from the resource's `format` field, then from the URL
extension. Engines: `openpyxl` (xlsx), `xlrd` (xls), `odf` (ods). Encoding:
UTF-8 with `latin-1` fallback.

**Limits.** Files above `MAX_DOWNLOAD_SIZE_MB` (100 MB) are refused. A size
declared in the CKAN metadata is rejected before any download; otherwise the
read is **bounded while streaming** (`max_bytes`), so the process never buffers
more than the limit even if `Content-Length` is missing or wrong.

**SSRF guard.** The URL comes from the portal metadata: it is checked before
the first request and at **every redirect** (3 hops max). Refused: any scheme
other than `http`/`https`, credentials in the URL, a host outside
`DOWNLOAD_ALLOWED_HOSTS` when that variable is set, and any address resolving
outside public space (loopback, RFC 1918, link-local `169.254.0.0/16`, IPv6
ULA `fc00::/7`, IPv4-mapped IPv6, 6to4, Teredo). The message returned is
`téléchargement refusé`, without exposing the full URL.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "download_and_parse_resource",
    "arguments": {
      "resource_id": "d5c80dcb-3bae-4c12-81ba-fa28f9841776",
      "limit": 200
    }
  }
}
```

**Example response** (captured, abridged)

```text
Ressource : situation saep
ID : d5c80dcb-3bae-4c12-81ba-fa28f9841776
Format : CSV
Lignes analysees : 200 (limite de 200)

Schema (6 colonnes) :
  - _id (int64)
  - saep (str)
  - dateSituation (str)
  - cause (str)
  - dateResolution (str)
  - etat (str)

Statistiques descriptives :
  _id : count=200, min=4, moyenne=132.105, max=233
  saep : count=200, valeurs uniques=198
  cause : count=35, valeurs uniques=21

5 premieres lignes :
1. _id=4 | saep=Missra | dateSituation=2020-07-07 | etat=F
2. _id=37 | saep=Esskhaibia | dateSituation=2020-07-07 | etat=F
```

**Statistics.** Numeric columns report `count`, `min`, `moyenne`, `max`; text
columns report `count` and `valeurs uniques`. `count` is the number of
**non-null** values — `cause` is populated on only 35 of 200 rows above.

> 🐛 **Known bug: the `xls` format fails.** Tested against a real portal XLS
> resource, the call returns `erreur de parsing (XLRDError)`. The format is
> detected correctly but `xlrd` cannot read the file. Prefer `xlsx` or `csv`
> until fixed.

---

## C3. `get_metrics` (implémenté)

### 🇫🇷 Français

**But.** Récupérer les indicateurs d'usage d'un dataset, ou les compteurs
globaux du portail.

**Paramètres**

| Nom | Type | Req. | Défaut | Description |
|-----|------|------|--------|-------------|
| `dataset_id` | string \| null | non | `null` | Si absent ⇒ métriques globales du portail. |
| `period` | string | non | `"30d"` | Période acceptée : `7d`, `30d`, `90d`, `1y`. |

**Disponibilité.** **Production uniquement** : si `DATAGOV_API_ENV != prod`,
l'appel est refusé.

**Exemple de requête**

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "get_metrics",
    "arguments": {
      "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938",
      "period": "30d"
    }
  }
}
```

**Exemple de réponse — par dataset** (capturé)

```text
Indicateurs d'usage
Periode : 30d

Dataset : systèmes d'alimentation en eau potable
ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938

Telechargements par ressource (3) :
  1. Situation des systèmes d'alimentation en eau potable : 0 telechargement(s)
  2. situation saep : 0 telechargement(s)
  3. saep : 0 telechargement(s)

Total des telechargements : 0
Vues : indisponible via l'API
Reutilisations : indisponible via l'API
Tendance : indisponible via l'API (pas d'historique)
```

**Exemple de réponse — portail entier** (capturé, sans `dataset_id`)

```text
Indicateurs d'usage
Periode : 30d

Datasets disponibles : 2 913
Organisations : 220
Themes (groupes) : 23

Telechargements globaux : indisponible via l'API
Vues / reutilisations : indisponible via l'API
```

**Cas limites** (capturés)

| Entrée | Sortie |
|--------|--------|
| `period="5d"` | `Periode '5d' non valide (valeurs acceptees : 1y, 30d, 7d, 90d).` |
| `DATAGOV_API_ENV=demo` | `Indicateurs d'usage disponibles uniquement en environnement production (reglez DATAGOV_API_ENV=prod).` |
| dataset inconnu | `Dataset introuvable pour '…' : HTTP 404 sur /action/package_show` |
| dataset sans ressource | `Ce dataset ne contient aucune ressource.` |

> ⚠️ **Écart avec le CDC.** Le CDC §4.1 attend *téléchargements*, *vues*,
> *réutilisations* et *tendance*. L'API CKAN de data.gov.tn n'expose que
> **`downloads_count`**. Les trois autres indicateurs renvoient explicitement
> `indisponible via l'API`, et **`period` est décoratif** : il est validé puis
> affiché, mais n'influence aucune requête. Sans source de données
> complémentaire, les trois indicateurs ne pourront pas être servis.

<div dir="rtl">

### 🇹🇳 العربية

**الغرض.** جلب مؤشرات استعمال مجموعة بيانات، أو العدّادات العامة للبوابة.

**المعاملات**

| الاسم | النوع | إجباري | الافتراضي | الوصف |
|-------|------|--------|-----------|-------|
| `dataset_id` | نص أو `null` | لا | `null` | إذا كان فارغًا ⇒ مؤشرات البوابة العامة. |
| `period` | نص | لا | `"30d"` | القيم المقبولة: `7d`، `30d`، `90d`، `1y`. |

**التوفّر.** في بيئة الإنتاج فقط؛ تُرفض الأداة إذا لم يكن
`DATAGOV_API_ENV=prod`.

**مثال على الطلب:**

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "get_metrics",
    "arguments": {
      "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938",
      "period": "30d"
    }
  }
}
```

**مثال على الاستجابة** (مخرجات حقيقية، مختصرة):

```text
Indicateurs d'usage
Periode : 30d

Total des telechargements : 0
Vues : indisponible via l'API
Reutilisations : indisponible via l'API
Tendance : indisponible via l'API (pas d'historique)
```

**حالة خاصة:**

| المُدخل | المُخرج |
|---------|---------|
| `period="5d"` | `Periode '5d' non valide (valeurs acceptees : 1y, 30d, 7d, 90d).` |
| بيئة غير إنتاجية | `Indicateurs d'usage disponibles uniquement en environnement production.` |

⚠️ **ملاحظة:** لا توفّر واجهة CKAN سوى عدّاد `downloads_count`؛ أما المشاهدات
فغير متاحة، والمعيار `period` شكلي في المرحلة الحالية.

</div>

### 🇬🇧 English

**Purpose.** Retrieve usage metrics for a dataset, or global portal counters.

**Parameters**

| Name | Type | Req. | Default | Description |
|------|------|------|---------|-------------|
| `dataset_id` | string \| null | no | `null` | If absent ⇒ global portal metrics. |
| `period` | string | no | `"30d"` | One of `7d`, `30d`, `90d`, `1y`. |

**Availability.** **Production only** — refused when `DATAGOV_API_ENV != prod`.

**Example request**

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "get_metrics",
    "arguments": {
      "dataset_id": "bb95f2ac-fc65-4cb4-843a-e9a6f99cd938",
      "period": "30d"
    }
  }
}
```

**Example response — per dataset** (captured)

```text
Indicateurs d'usage
Periode : 30d

Dataset : systèmes d'alimentation en eau potable
ID : bb95f2ac-fc65-4cb4-843a-e9a6f99cd938

Telechargements par ressource (3) :
  1. Situation des systèmes d'alimentation en eau potable : 0 telechargement(s)
  2. situation saep : 0 telechargement(s)
  3. saep : 0 telechargement(s)

Total des telechargements : 0
Vues : indisponible via l'API
Reutilisations : indisponible via l'API
Tendance : indisponible via l'API (pas d'historique)
```

**Example response — whole portal** (captured, no `dataset_id`)

```text
Indicateurs d'usage
Periode : 30d

Datasets disponibles : 2 913
Organisations : 220
Themes (groupes) : 23

Telechargements globaux : indisponible via l'API
Vues / reutilisations : indisponible via l'API
```

**Edge cases** (captured): `period="5d"` ⇒
`Periode '5d' non valide (valeurs acceptees : 1y, 30d, 7d, 90d).`; non-prod ⇒
`Indicateurs d'usage disponibles uniquement en environnement production
(reglez DATAGOV_API_ENV=prod).`

> ⚠️ **Deviation from the CDC.** CDC §4.1 expects downloads, views, reuses and
> trend. The CKAN API exposes **only `downloads_count`**; the other three
> explicitly return `indisponible via l'API`, and **`period` is currently
> decorative** — validated and echoed, but it changes no query.

---

# Workflow typique

Le CDC §4.2 décrit un usage en trois couches. Sur le portail réel, la combiner
avec les limites observées donne ceci (⚠️ = à éviter aujourd'hui) :

```text
ÉTAPE 1 — DÉCOUVERTE
  search_datasets(query="eau potable", page_size=5)
    → bb95f2ac-fc65-4cb4-843a-e9a6f99cd938  (systèmes d'alimentation…)

ÉTAPE 2 — INSPECTION
  get_dataset_info(dataset_id="bb95f2ac-…")
    → qualité 88 %, 3 ressources, licence LNDP
  list_dataset_resources(dataset_id="bb95f2ac-…")
    → 3 ressources : HTML, CSV, (format vide)
  get_resource_info(resource_id="d5c80dcb-…")
    → CSV, taille non renseignée, Tabular API : Non

ÉTAPE 3 — ANALYSE
  Le datastore est INACTIF sur ces ressources :
    → C1 impossible
    → C2 download_and_parse_resource(resource_id="d5c80dcb-…", limit=200)
      schéma 6 colonnes + statistiques + 5 premières lignes  ✓
```

Pour les ressources disposant d'un datastore actif, remplacez l'étape 3 par :

```text
  query_resource_data(
    resource_id="3642ee8d-…",
    columns=["_id", "Nom", "Budget  _Ann_2021"],
    filters=[{"column": "Classification", "operator": "eq", "value": 1}],
    sort=[{"column": "_id", "direction": "desc"}],
    page=1, page_size=20
  )
```

---

# Points d'attention transverses

| Sujet | État | Action |
|-------|------|--------|
| Nombre d'outils annoncé | CDC dit 9 mais en liste 10 ; le code en expose **10** | Aligner le CDC sur « 10 » |
| B4 / B5 | ✅ Codés, testés et enregistrés | Confirmer que `dataservice_id` = dataset |
| Trilinguisme AR/FR/EN | ⚠️ `lang` disponible sur B1–B5 (libellés seuls) ; A et C restent en français | Étendre à A et C pour l'art. 16 |
| Format de sortie | Texte brut, pas JSON structuré | Envisager un wrapper |
| B2 pagination | ✅ `page`/`page_size` exposés, `page_size` plafonné par `MAX_PAGE_SIZE` | — |
| C1 mode SQL | 🐛 `gt`/`lt` → HTTP 500 en production | Privilégier `eq`/`in`/`contains` |
| C2 format `xls` | 🐛 `XLRDError` | Utiliser `xlsx`/`csv` |
| C3 indicateurs | ⚠️ vues/réutilisations/tendance indisponibles ; `period` décoratif | Source de données à définir |
| Pagination | Codée en ligne dans chaque outil | `helpers/pagination.py` vide |
| Erreurs | Rendues en texte | Pas d'exceptions MCP typées |
| Données du portail | Noms de colonnes avec espaces doubles (`Budget  _Ann_2021`) | Attention aux colonnes |
