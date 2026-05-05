# 🔬 Rétroconception Hardware par Imagerie RX

> **Domaine :** Analyse de systèmes & Sécurité offensive  
> **Méthode :** Radiotomographie non-destructive  
> **Cible :** Circuits intégrés et PCB multicouches

---

## 📑 Sommaire
- [1. Introduction à la rétroconception](#-1-introduction-à-la-rétroconception)
- [2. Anatomie des images RX](#-2-anatomie-des-images-rx)
- [3. Mémoires eMMC & Flash](#-3-mémoires-emmc--flash)
- [4. Protocoles de communication](#-4-protocoles-de-communication)
- [5. Analyse & Identification](#-5-analyse--identification)
- [6. Études de cas (Real-world)](#-6-études-de-cas-real-world)
- [7. Défis & Évolutions](#-7-défis--évolutions)

---

## 🛠 1. Introduction à la rétroconception

La **rétroconception** (ou *reverse engineering*) hardware est l'art de déconstruire un système pour en comprendre les secrets sans les plans originaux.

### Les deux approches majeures
| Approche | Méthode | Impact |
| :--- | :--- | :--- |
| **Destructive** | Décapsulation chimique, polissage de couches | Destruction définitive du composant |
| **Non-destructive** | **Imagerie RX / Tomographie** | Composant intact & fonctionnel après analyse |

> [!IMPORTANT]
> **Pourquoi privilégier les RX ?**
> - **Récupération Forensic :** Extraire des données d'un appareil physiquement endommagé.
> - **Audit de Sécurité :** Détection de *Hardware Trojans* (implants espions).
> - **Anti-Contrefaçon :** Vérifier que la structure interne correspond aux spécifications du fabricant.

---

## 📸 2. Anatomie des images RX

La tomographie permet une vue 3D en "tranches". La règle d'or : **Plus le matériau est dense, plus il apparaît clair (blanc).**

### Guide visuel des densités
| Aspect | Matériau | Exemples types |
| :--- | :--- | :--- |
| ⚫ **Noir** | Air / Vide | Espaces entre composants, bulles d'air |
| 🌚 **Gris foncé** | Plastique / Résine | Boîtiers (package) de puces |
| 🔘 **Gris moyen** | Silicium | Le "Die" (cœur) de la puce |
| ⚪ **Gris clair** | Cuivre | Pistes, Vias, Plans de masse |
| ⭐ **Blanc Brillant** | Or / Plomb / Tungstène | Soudures (BGA), Fils de bonding, Blindages |

---

## 💾 3. Mémoires eMMC & Flash

L'**eMMC** (*Embedded MultiMediaCard*) est le standard des systèmes embarqués (mobiles, IoT). Elle regroupe un contrôleur et de la mémoire NAND.

### Évolution des performances
| Version | Débit Max | Usage type |
| :--- | :--- | :--- |
| **eMMC 4.4** | 52 MB/s | Anciens GPS, domotique simple |
| **eMMC 5.0** | 250 MB/s | Smartphones entrée de gamme |
| **eMMC 5.1** | 400 MB/s | Tablettes, Dashcams modernes |

> [!TIP]
> **Reconnaissance RX :** Une eMMC se reconnaît à sa grille de billes **BGA** parfaitement alignée et à la présence d'un petit contrôleur souvent visible sur l'une des couches supérieures du "die".

---

## 📡 4. Protocoles de communication

### Le Bus SD (Secure Digital)
C'est le lien vital entre le CPU et le stockage. On cherche souvent à intercepter ces signaux :
* `CLK` : Horloge (synchronisation).
* `CMD` : Envoi des instructions (ex: "Lire secteur 0").
* `DAT0-3` : Transport des données sur 1 ou 4 bits.

### Le Standard ONFI
Le standard **ONFI** (*Open NAND Flash Interface*) normalise les puces NAND nues.
* **Intérêt :** Rendre les puces interchangeables.
* **Observation :** Sous RX haute résolution, on peut parfois distinguer la signature lithographique du fabricant.

---

## 🔍 5. Analyse & Identification

### Logiciels de référence
* 🔲 **VGI Studio** : Le "Photoshop" industriel pour la reconstruction 3D.
* 🐲 **Dragonfly CT** : Idéal pour segmenter automatiquement les différents matériaux.
* 🛠️ **ImageJ / FIJI** : Outil Open Source puissant pour les mesures de précision en 2D.

### Critères d'identification rapide
* **eMMC** : Présence d'un blindage métallique périphérique.
* **NAND Brute** : Densité de billes très élevée, absence de logique de contrôle complexe.
* **Connecteur SD** : Structure mécanique visible avec ressorts et contacts épais.

---

## 🕵️ 6. Études de cas (Real-world)

#### 📱 Cas n°1 : Le Smartphone "Briké"
* **Problème :** Carte mère grillée, impossible de démarrer.
* **Solution :** Localisation de l'eMMC via RX -> Extraction par dessoudage infra-rouge -> Lecture directe sur un programmateur Z3X/Medusa.

#### 🛡️ Cas n°2 : L'Implant Espion
* **Problème :** Un routeur sécurisé semble exfiltrer des données.
* **Découverte :** Les RX révèlent un composant au **Tungstène** soudé en "sandwich" sous le processeur, totalement invisible à l'inspection visuelle classique.

#### 🚫 Cas n°3 : La Fraude aux Capacités
* **Découverte :** Une clé USB vendue pour 512 Go ne contient en réalité qu'une puce de 4 Go. Pour tromper le client, le fabricant a ajouté des **plaques de plomb** pour simuler le poids d'un produit haut de gamme.

---

## 🚀 7. Défis & Évolutions

- [x] **Miniaturisation :** Les gravures en 3nm sont invisibles au RX conventionnel (limite physique).
- [x] **Complexité PCB :** Les cartes à 16+ couches créent des artefacts de superposition difficiles à filtrer.
- [ ] **UFS (Universal Flash Storage) :** Le successeur de l'eMMC. Utilise des paires différentielles haute vitesse, rendant le "sniffing" passif très complexe.
- [ ] **3D NAND :** L'empilement vertical de 200+ couches de cellules crée une opacité uniforme difficile à analyser en profondeur.

---
*Document créé pour le stockage de cours GitHub | 2024*
