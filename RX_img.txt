Cours : Rétroconception Hardware par Imagerie RX
1. Introduction à la rétroconception hardware
Définition

La rétroconception (ou reverse engineering) hardware est le processus d'analyse d'un système électronique pour comprendre son architecture, ses composants et son fonctionnement, sans disposer des plans d'origine. Elle peut être destructive (décapsulation) ou non destructive (imagerie RX, rayons X).
Importance

    Récupération de données : Sur composant défaillant (lecture directe des puces mémoire).

    Sécurité informatique : Détection de backdoors, de hardware Trojans, ou analyse de puces sécurisées.

    Vérification d'intégrité : Contrôle de conformité par rapport aux spécifications.

    Obsolescence : Compréhension de composants anciens pour maintenance.

Introduction à la radiotomographie RX

La tomographie par rayons X permet de reconstruire en 3D la structure interne d'un circuit imprimé. Contrairement à une simple radiographie 2D, la tomographie donne accès à la profondeur des couches. Les images sont en niveaux de gris : plus le matériau est dense (plomb, cuivre, tungstène), plus il absorbe les RX et apparaît clair.
2. Anatomie des images RX
Identification des différentes couches

Un circuit multicouche standard (ex. : carte mère) contient :

    Couche supérieure : composants CMS, pistes de signal.

    Couches internes : plans de masse, plans d’alimentation, routage dense.

    Couche inférieure : connecteurs, pastilles de test.

Analyse des densités
Matériau	Densité	Aspect RX
Air / vide	faible	noir
Plastique (boîtier)	moyenne	gris foncé
Silicium (puce)	moyenne+	gris moyen
Cuivre (pistes, vias)	élevée	gris clair
Or / plomb (soudure)	très élevée	blanc éclatant

Les vias apparaissent comme des anneaux clairs. Les balles de BGA (soudure sous puce) sont très visibles : leur alignement et leur forme indiquent la qualité du brasage.
3. Mémoires eMMC
Définition et fonctionnement

eMMC (Embedded MultiMediaCard) = puce intégrant un contrôleur flash NAND + la mémoire NAND elle-même dans un seul boîtier (souvent BGA). Elle communique via un bus MMC standard.
Caractéristiques techniques

    Interfaces : 8 bits (largeur de données), horloge jusqu'à 200 MHz (HS400).

    Commandes : lecture/écriture par blocs, gestion des bad blocks, wear leveling.

    Boot : zones boot1 et boot2 (pour le chargeur d'amorçage).

Versions et capacités
Version	Débit max	Capacité typique
eMMC 4.4	52 MB/s	2–32 Go
eMMC 5.0	250 MB/s	8–128 Go
eMMC 5.1	400 MB/s	16–512 Go

En image RX, une eMMC se reconnaît à son boîtier BGA uniforme (billes sous la puce) et à une puce contrôleur visible parfois sur le dessus (émulsion de silicium).
4. Protocoles SD (Secure Digital)
Présentation

Le protocole SD est dérivé du MMC mais avec ajout de sécurité (DRM, chiffrement). C'est un bus série synchrone (1 bit, 4 bits) avec lignes : CMD (commandes), CLK, DAT0-3.
Versions et caractéristiques
Type	Capacité	Système de fichiers	Tension
SD (v1)	≤ 2 Go	FAT16	3,3 V
SDHC (v2)	4–32 Go	FAT32	3,3 V
SDXC (v3)	64 Go – 2 To	exFAT	3,3 V
SDUC (v7)	≤ 128 To	exFAT	3,3 V

En rétroconception, on cherche souvent à intercepter le bus SD entre un processeur hôte et une eMMC (qui utilise aussi un protocole compatible SD/MMC).
5. Protocole ONFI (Open NAND Flash Interface)
Principe et objectifs

ONFI est un standard ouvert pour interfacer des puces NAND brutes. Il normalise :

    Les broches (8/16 bits)

    Les commandes (lecture, programmation, effacement)

    Les timings (DDR possible)

    La gestion des bad blocks et de l'ECC

Avantages de l’interopérabilité

Avant ONFI, chaque fabricant (Samsung, Toshiba, Hynix) avait son interface propriétaire. ONFI permet à n’importe quel contrôleur conforme de piloter n’importe quelle puce ONFI. En rétroconception, la présence du logo ONFI sur une image RX aide à identifier une puce NAND.
6. Analyse de l’image RX pour l’identification des composants
Outils logiciels

    VGI Studio (Volume Graphics) : traitement tomographique 3D, mesures, segmentation.

    DCT (Dragonfly CT) : analyse multi-énergies.

    ImageJ/FIJI : open source, pour des analyses 2D de base.

Techniques d’identification
Composant	Critère RX
eMMC	BGA avec anneau métallique périphérique (blindage), épaisseur totale 1–1,5 mm
NAND brute	Puce rectangulaire, sans contrôleur intégré, densité de billes élevée
Contrôleur SD	Puce souvent plus petite, parfois logo fabricant visible (lithographie)
Connecteur SD	Contacts métalliques épais, ressort visible (image RX haute résolution)

On utilise la différence de contraste pour isoler les plans : par exemple, un plan de masse apparaît comme une zone homogène claire, tandis que les pistes de signal sont des lignes fines.
7. Études de cas et applications
Cas 1 : Récupération de données sur smartphone mort

Un smartphone ne s’allume plus. On réalise une tomographie RX de la carte mère. On identifie la puce eMMC (position, orientation des billes). On mesure les connexions puis on désoude la puce pour la lire sur un adaptateur eMMC dédié.
Cas 2 : Sécurité – recherche de hardware Trojan dans un module IoT

Analyse RX d’un module Wi-Fi suspect. On découvre une puce supplémentaire non référencée entre l’antenne et le processeur. L’analyse de densité RX montre qu’elle contient du tungstène (masque actif), probablement une puce espion.
Cas 3 : Intégrité – vérification de contrefaçon

Une entreprise achète des eMMC “authentiques”. L’image RX révèle que le boîtier contient une NAND de capacité moindre + des pastilles de remplissage (plomb) pour simuler le poids et la densité.
8. Questions avancées
Défis et limites de la rétroconception par RX

    Résolution : Les nœuds de gravure submicroniques (7 nm, 3 nm) ne sont pas visibles – nécessité d’un MEB ou d’une décapsulation.

    Superposition : Dans un circuit très dense, les couches se chevauchent, rendant l’interprétation difficile.

    Absence de fonction logique : Les images RX montrent les structures physiques, pas les états électriques ou le firmware.

    Temps de reconstruction : Une tomographie haute résolution peut nécessiter plusieurs heures de calcul.

Évolutions récentes

    UFS (Universal Flash Storage) : remplace eMMC sur haut de gamme (débit > 1 Go/s, bus série différencié). Sa structure en image RX est plus complexe (plus de broches, signaux à haute fréquence).

    NVMe sur puce : permet de piloter directement des NAND via PCIe.

    3D NAND : les cellules sont empilées verticalement (jusqu’à 200+ couches). En RX, cela se traduit par une densité de matière uniforme en épaisseur, difficile à distinguer de simples condensateurs.

    Multiplexage temporel des bus : rend l’observation statique RX insuffisante – besoin de combiner avec analyse de signal (logique).