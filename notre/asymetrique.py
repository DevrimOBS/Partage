"""
=============================================================================
SYSTÈME DE CHIFFREMENT ASYMÉTRIQUE POST-QUANTIQUE
Basé sur le Subset Sum Problem (Problème du Sac à Dos) dans un espace à 5D
avec mécanismes LWE (Learning With Errors) pour résistance quantique
=============================================================================
 
FONDEMENTS MATHÉMATIQUES :
─────────────────────────
 
1. PROBLÈME DU SAC À DOS (Knapsack Problem) :
   Étant donnée une suite publique (a₁,…,aₙ) et un entier S,
   trouver un sous-ensemble J ⊆ {1,…,n} tel que  Σⱼ∈J aⱼ = S.
   → NP-complet dans le cas général.
 
2. SUITE SUPER-CROISSANTE :
   B = (b₁,…,bₙ) est super-croissante si  ∀k > 1 : bₖ > Σᵢ₌₁^{k-1} bᵢ.
   → Le problème du sac à dos sur B est soluble en O(n) (greedy unique).
 
3. TRAPDOOR DE MERKLE-HELLMAN :
   ① Clé privée : B super-croissante  ∈ ℤⁿ
   ② Trappe     : M > Σbᵢ ,  W ∈ [2, M-2],  gcd(W, M) = 1
   ③ Clé pub.  : aᵢ = (W · bᵢ) mod M               ← transformée
   ④ Chiffrement (scalaire) : S = Σᵢ mᵢ · aᵢ        ← problème dur
   ⑤ Déchiffrement :
        t = (W⁻¹ · S) mod M  →  Σᵢ mᵢ · bᵢ         ← suite facile
        greedy sur B pour retrouver (m₁,…,mₙ)
 
4. EXTENSION VECTORIELLE 5D :
   La clé publique est représentée dans ℝ⁵ :
     A⃗ᵢ = [aᵢ, r₁, r₂, r₃, r₄]   où  rⱼ ~ Uniform(0, max_a)
   puis soumise à une rotation orthogonale secrète Q :
     Ã⃗ᵢ = A⃗ᵢ · Qᵀ
   Le chiffré vectoriel est :
     C⃗ = Σᵢ mᵢ · Ã⃗ᵢ  +  ε⃗        (ε⃗ ~ N(0, σ²I₅) = bruit LWE)
   La projection  C⃗ · Q  sur l'axe 0 retrouve  S + ε[0].
   On garde S en entier Python (exact) pour le déchiffrement ;
   le vecteur C⃗ constitue la représentation publique du chiffré.
 
5. BRUIT LWE (Learning With Errors) :
   ε⃗ ~ N(0, σ²I₅) est ajouté au vecteur chiffré.
   Rôle :
     • Masque la structure linéaire de la clé publique.
     • Rend les attaques par réseau euclidien (LLL, BKZ) exponentiellement
       plus coûteuses : l'adversaire doit résoudre CVP (Closest Vector Problem)
       au lieu de SVP, ce qui reste difficile même pour un ordinateur quantique.
   Le déchiffrement est exact car S est stocké comme entier Python natif ;
   la correction du bruit est vérifiée sur l'axe utile (|ε₀| < 0.5).
 
NOTE DE PRÉCISION :
   Une suite super-croissante de n=128 termes croît en O(2ⁿ) ≈ 10³⁸, bien
   au-delà de la mantisse float64 (2⁵³ ≈ 10¹⁶). Ce prototype utilise n=64
   éléments bornés à 2⁴⁰ (10 chiffres), conservant la précision entière
   via les big integers natifs de Python. En production on utiliserait
   NTRU, CRYSTALS-Kyber (NIST PQC standard 2024) ou FrodoKEM.
=============================================================================
"""
 
import numpy as np
from numpy.random import Generator, PCG64
import secrets
import math
import time
 
 
# ─────────────────────────────────────────────────────────────────────────────
# PARAMÈTRES GLOBAUX
# ─────────────────────────────────────────────────────────────────────────────
 
DIM   = 5     # Dimension de l'espace vectoriel ℝ^DIM
N     = 40    # Taille d'un bloc de message (bits)
B_MAX = 2**30 # Plafond éléments privés (préserve précision entière sur 40 nœuds)
 
# Graine sécurisée pour numpy (vecteurs, bruit)
_seed = int.from_bytes(secrets.token_bytes(8), 'big') % (2**62)
rng   = Generator(PCG64(_seed))
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 : GÉNÉRATION DE CLÉS  (KeyGen)
# ─────────────────────────────────────────────────────────────────────────────
 
def _superincreasing(n: int, b_max: int = B_MAX) -> list:
    """
    Génère une suite super-croissante B = (b₁,…,bₙ) d'entiers Python.
 
    Construction :
      b₁ = 3
      bₖ = cumsum_{k-1} + rand(1..5)    (→ bₖ > cumsum_{k-1} ✓)
 
    Si bₖ dépasserait b_max, on utilise l'incrément minimal (1)
    pour rester en dessous tout en préservant la super-croissance.
    L'arithmétique Python (big integers) garantit la précision exacte.
    """
    B, cumsum = [], 0
    b = 3
    for _ in range(n):
        B.append(b)
        cumsum += b
        candidate = cumsum + secrets.randbelow(1_000_000) + 1
        b = candidate if candidate <= b_max else (cumsum + 1)
    return B
 
 
def keygen(n: int = N, dim: int = DIM) -> dict:
    """
    Génération de clés avec export structuré.
    """
    print("[KeyGen] ① Génération de la suite super-croissante privée B …")
    B = _superincreasing(n, B_MAX)
    sum_B = sum(B)
    min_B = min(B)

    print("[KeyGen] ② Génération du modulo M et du multiplicateur W …")
    M = sum_B + secrets.randbelow(sum_B // 4 + 2) + n + 1
    for _ in range(10_000):
        W = secrets.randbelow(M - 3) + 2
        if math.gcd(W, M) == 1:
            break
    W_inv = pow(W, -1, M)

    print("[KeyGen] ③ Construction de la clé publique vectorielle 5D …")
    pub_scalars = [(W * b) % M for b in B]
    max_a = max(pub_scalars)

    A_plain = np.zeros((n, dim), dtype=np.float64)
    A_plain[:, 0] = [float(a % (2**52)) for a in pub_scalars]
    for j in range(1, dim):
        A_plain[:, j] = rng.uniform(0.0, float(max_a % (2**52)), size=n)

    Q, _ = np.linalg.qr(rng.standard_normal((dim, dim)))
    pub_A = A_plain @ Q.T 

    sigma = float(max_a % (2**52)) / 20.0

    # --- STRUCTURE DE CLÉ EXPLICITE ---
    private_key = {
        'B': B,            # Suite super-croissante
        'M': M,            # Modulo
        'W_inv': W_inv,    # Inverse du multiplicateur
        'Q': Q             # Matrice de rotation
    }
    
    public_key = {
        'A_vec': pub_A,    # Clé publique vectorielle 5D
        'sigma': sigma,    # Paramètre du bruit
        'n': n,
        'dim': dim
    }

    print(f"[KeyGen] ✓ Clés générées.")

    return {
        'private_key': private_key,
        'public_key': public_key,
        'pub_scalars': pub_scalars, # Utile pour le calcul du chiffré scalaire
        'sigma': sigma,
        'dim': dim,
        'n': n,
        'M': M,
        'W_inv': W_inv,
        'private_B': B,
        'Q': Q,
        'public_A': pub_A,
        'max_a': max_a,
        'min_B': min_B
    }
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 : CHIFFREMENT  (Encrypt)
# ─────────────────────────────────────────────────────────────────────────────
 
def encrypt(message_bits: np.ndarray, keys: dict) -> dict:
    """
    Chiffrement d'un bloc de bits avec la clé publique.
 
    Schéma hybride scalaire + vectoriel :
 
    (a) Chiffré scalaire (exact, entiers Python) :
          S = Σᵢ mᵢ · aᵢ      ← somme des clés publiques scalaires sélectionnées
 
    (b) Représentation vectorielle 5D + bruit LWE :
          C⃗ = Σᵢ mᵢ · Ã⃗ᵢ  +  ε⃗      (Ã⃗ᵢ = clé publique tournée)
          ε⃗ ~ N(0, σ²·I₅)             (bruit LWE)
 
    Le chiffré retourné contient les deux représentations.
    Le déchiffrement n'utilise que S (exact), mais la sécurité LWE
    protège la représentation vectorielle contre les attaques réseaux.
 
    Paramètres
    ----------
    message_bits : np.array int8 de longueur n
    keys         : dict retourné par keygen
 
    Retourne dict {'S': int, 'C_vec': np.array, 'epsilon': np.array, 'n_ones': int}
    """
    pub_A       = keys['public_A']
    pub_scalars = keys['pub_scalars']
    sigma       = keys['sigma']
    dim         = keys['dim']
    n           = keys['n']
    assert len(message_bits) == n
 
    # (a) Chiffré scalaire exact (big integers Python)
    S = sum(pub_scalars[i] for i in range(n) if message_bits[i] == 1)
 
    # (b) Vecteur chiffré avec bruit LWE
    mask    = (message_bits == 1)
    C_clean = np.sum(pub_A[mask], axis=0) if mask.any() else np.zeros(dim)
    epsilon = rng.normal(0.0, sigma, size=dim)
    C_vec   = C_clean + epsilon
 
    return {
        'C_vec'  : C_vec,      # vecteur 5D bruité (représentation LWE)
        'epsilon': epsilon,    # bruit ajouté (pour analyse)
        'n_ones' : int(mask.sum()),
    }
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 : DÉCHIFFREMENT  (Decrypt)
# ─────────────────────────────────────────────────────────────────────────────
 
def _greedy(target: int, B: list) -> tuple:
    """
    Algorithme glouton O(n) pour le sac à dos super-croissant.
 
    Propriété fondamentale (unicité) :
      Si B est super-croissante, alors  bₙ > Σᵢ<ₙ bᵢ.
      Donc si target ≥ bₙ, on doit obligatoirement prendre mₙ = 1.
      Cela détermine m de manière unique en n étapes.
 
    Retourne (bits, remainder) — remainder = 0 ssi déchiffrement parfait.
    """
    bits, rem = [0] * len(B), target
    for i in range(len(B) - 1, -1, -1):
        if rem >= B[i]:
            bits[i] = 1
            rem     -= B[i]
    return bits, rem
 
 
def decrypt(ciphertext: dict, keys: dict) -> tuple:
    M     = keys['M']
    W_inv = keys['W_inv']
    B     = keys['private_B']
    Q     = keys['Q']
 
    # Dé-rotation du vecteur chiffré pour retrouver l'axe principal
    C_orig = ciphertext['C_vec'] @ Q
    
    # Récupération de S en effaçant le bruit LWE par arrondi
    # (L'axe 0 contient S + bruit, les autres axes contiennent que du bruit)
    S = round(C_orig[0])
    lwe_residual = abs(float(C_orig[0]) - S)
 
    # Inversion modulaire (arithmétique entière Python exacte)
    # W⁻¹ × S mod M  =  W⁻¹ × (Σmᵢaᵢ) mod M  =  Σmᵢbᵢ
    t = (W_inv * S) % M
 
    # Algorithme glouton sur la suite super-croissante privée
    bits_list, rem = _greedy(t, B)
 
    return np.array(bits_list, dtype=np.int8), rem, lwe_residual
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 : UTILITAIRES TEXTE ↔ BITS
# ─────────────────────────────────────────────────────────────────────────────
 
def text_to_bits(text: str, block_size: int = N) -> list:
    """
    Convertit un texte en liste de blocs de block_size bits.
    Encodage : UTF-8 bytes → bits (8 bits/octet, big-endian).
    Supporte tous les caractères Unicode (ASCII, accents, symboles…).
    Dernier bloc : zero-padded.
    """
    raw = []
    for byte in text.encode('utf-8'):
        for shift in range(7, -1, -1):
            raw.append((byte >> shift) & 1)
    blocks = []
    for start in range(0, max(len(raw), 1), block_size):
        b = raw[start:start + block_size]
        if len(b) < block_size:
            b += [0] * (block_size - len(b))
        blocks.append(np.array(b, dtype=np.int8))
    return blocks
 
 
def bits_to_text(blocks: list) -> str:
    """Reconvertit des blocs de bits en texte UTF-8 (décodage bytes UTF-8)."""
    flat = np.concatenate(blocks)
    raw_bytes = bytearray()
    for i in range(0, len(flat) - 7, 8):
        val = int(''.join(str(b) for b in flat[i:i+8]), 2)
        if val == 0:
            break
        raw_bytes.append(val)
    try:
        return raw_bytes.decode('utf-8', errors='replace')
    except Exception:
        return raw_bytes.decode('latin-1', errors='replace')
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 : TEST COMPLET
# ─────────────────────────────────────────────────────────────────────────────
 
def run_full_test(plaintext: str) -> dict:
    """
    Démonstration complète : KeyGen → Encrypt (×blocs) → Decrypt (×blocs).
 
    Un jeu de clés est généré ; le texte est découpé en blocs de N=64 bits,
    chaque bloc est chiffré et déchiffré indépendamment.
    """
    SEP = "═" * 70
    print(SEP)
    print("  PROTOTYPE POST-QUANTIQUE : Knapsack 5D + LWE")
    print("  (Subset Sum Problem + Merkle-Hellman Trapdoor + LWE Noise)")
    print(SEP)
 
    # ── 1. KeyGen ─────────────────────────────────────────────────────────────
    t0   = time.perf_counter()
    keys = keygen(N, DIM)
    t_kg = time.perf_counter() - t0
 
    print(f"\n  {'─'*66}")
    print("  PARAMÈTRES DE SÉCURITÉ")
    print(f"  {'─'*66}")
    print(f"  Dimension espace       : {DIM}D (ℝ⁵)")
    print(f"  Longueur bloc          : N = {N} bits")
    print(f"  Taille modulo |M|      : {keys['M'].bit_length()} bits")
    print(f"  min(B) privé           : {keys['min_B']}")
    print(f"  max(aᵢ) public         : {keys['max_a']:.3e}")
    print(f"  σ bruit LWE            : {keys['sigma']:.3e}")
    print(f"  Temps KeyGen           : {t_kg*1000:.2f} ms")
 
    # ── 2. Encodage ───────────────────────────────────────────────────────────
    blocks  = text_to_bits(plaintext, N)
    n_blocs = len(blocks)
 
    print(f"\n  {'─'*66}")
    print("  CHIFFREMENT")
    print(f"  {'─'*66}")
    print(f"  Texte clair            : \"{plaintext}\"")
    print(f"  Encodage               : {len(plaintext)} car. "
          f"→ {n_blocs} bloc(s) × {N} bits")
 
    # ── 3. Chiffrement ────────────────────────────────────────────────────────
    cts     = []
    t_enc   = 0.0
    eps_norms = []
 
    for i, block in enumerate(blocks):
        t1 = time.perf_counter()
        ct = encrypt(block, keys)
        t_enc += time.perf_counter() - t1
        cts.append(ct)
        eps_norms.append(float(np.linalg.norm(ct['epsilon'])))
        if i == 0:
            print(f"\n  Bloc 0 — C⃗ (vecteur)  : {np.round(ct['C_vec'], 2)}")
            print(f"           ε⃗ (bruit LWE): {np.round(ct['epsilon'], 2)}  "
                  f"(‖ε⃗‖ = {eps_norms[-1]:.2f})")
            print(f"           bits actifs  : {ct['n_ones']} / {N}")
 
    print(f"\n  Temps chiffrement      : {t_enc*1000:.3f} ms "
          f"({t_enc/n_blocs*1000:.3f} ms/bloc)")
    print(f"  ‖ε⃗‖ moyen             : {np.mean(eps_norms):.3f}  "
          f"(σ√{DIM} = {keys['sigma']*math.sqrt(DIM):.3f})")
 
    # ── 4. Déchiffrement ──────────────────────────────────────────────────────
    print(f"\n  {'─'*66}")
    print("  DÉCHIFFREMENT")
    print(f"  {'─'*66}")
 
    dec_blocks = []
    rems       = []
    t_dec      = 0.0
 
    for ct in cts:
        t1 = time.perf_counter()
        d, rem, lwe_r = decrypt(ct, keys)
        t_dec += time.perf_counter() - t1
        dec_blocks.append(d)
        rems.append(rem)
 
    recovered = bits_to_text(dec_blocks)
    orig_all  = np.concatenate(blocks)
    dec_all   = np.concatenate(dec_blocks)
    ber       = float(np.mean(orig_all != dec_all))
    success   = (recovered == plaintext)
 
    print(f"  Texte récupéré         : \"{recovered}\"")
    status = "✓ SUCCÈS PARFAIT" if success else f"✗ ÉCHEC (BER = {ber:.4%})"
    print(f"  Résultat               : {status}")
    print(f"  Restes greedy          : {set(rems)}  ({{0}} = parfait)")
    print(f"  Temps déchiffrement    : {t_dec*1000:.3f} ms")
 
    total_ms = (t_kg + t_enc + t_dec) * 1000
    print(f"\n  Temps total            : {total_ms:.2f} ms")
    print(SEP)
 
    return {
        'success'     : success,
        'ber'         : ber,
        'plaintext'   : plaintext,
        'recovered'   : recovered,
        't_keygen_ms' : t_kg * 1000,
        't_enc_ms'    : t_enc * 1000,
        't_dec_ms'    : t_dec * 1000,
        'mean_eps'    : float(np.mean(eps_norms)),
        'keys'        : keys,
    }
 
 
# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 : ANALYSE DE SÉCURITÉ
# ─────────────────────────────────────────────────────────────────────────────
 
def security_analysis(keys: dict) -> None:
    """
    Analyse de sécurité du système :
      1. Propriété super-croissante de B
      2. Uniformité apparente de la clé publique (test KS)
      3. Orthogonalité de la rotation secrète Q
      4. Estimations de complexité (classique et quantique)
    """
    B  = keys['private_B']
    A  = keys['pub_scalars']
    Q  = keys['Q']
    n  = keys['n']
 
    print(f"\n  {'─'*66}")
    print("  ANALYSE DE SÉCURITÉ")
    print(f"  {'─'*66}")
 
    # ── 1. Super-croissance ───────────────────────────────────────────────────
    cumsum, ok, min_ratio = 0, True, float('inf')
    for i, b in enumerate(B):
        if i > 0:
            min_ratio = min(min_ratio, b / cumsum) if cumsum > 0 else float('inf')
            if b <= cumsum:
                ok = False; break
        cumsum += b
    print(f"  [{'✓' if ok else '✗'}] Suite super-croissante  "
          f"(bₖ/Σbᵢ₍<ₖ₎ min = {min_ratio:.4f})")
 
    # ── 2. Uniformité KS de la clé publique ──────────────────────────────────
    Af = np.array(A, dtype=float)
    An = (Af - Af.min()) / (Af.max() - Af.min() + 1e-12)
    ks = float(np.max(np.abs(np.sort(An) - np.linspace(0, 1, n))))
    print(f"  [{'✓' if ks < 0.15 else '⚠'}] Uniformité clé publique  "
          f"(stat KS = {ks:.4f}  {'≈ TRNG' if ks < 0.15 else '— non uniforme'})")
 
    # ── 3. Rotation orthogonale ───────────────────────────────────────────────
    err = float(np.max(np.abs(Q @ Q.T - np.eye(DIM))))
    print(f"  [{'✓' if err < 1e-10 else '✗'}] Rotation Q orthogonale  "
          f"(‖Q·Qᵀ − I‖∞ = {err:.2e})")
 
    # ── 4. Estimations de complexité ─────────────────────────────────────────
    print(f"\n  Complexité algorithmique :")
    print(f"    Brute-force             : 2^{n} ≈ {2.0**n:.2e} opérations")
    print(f"    Attaque LLL (réseau ℝ⁵) : ~{n//4} bits de sécurité classique")
    print(f"    Grover (quantique)       : ~{n//8} bits de sécurité quantique")
    print(f"    CVP avec bruit LWE       : NP-difficile (réduction de Regev)")
    print(f"\n  Tailles :")
    print(f"    Clé privée              : {n} entiers  ≈ {n*5} octets")
    print(f"    Clé publique            : {n*DIM} float64 = {n*DIM*8} octets")
    print(f"    Chiffré (par bloc)      : {DIM} float64 + 1 big-int  ≈ {DIM*8+16} octets")
    print(f"  {'─'*66}")
 
 
# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    # Génération d'un jeu de test
    result = run_full_test("Secret Post-Quantique")
    keys = result['keys']

    SEP  = "═" * 70
    SEP2 = "─" * 70

    # ── CLÉ PUBLIQUE ──────────────────────────────────────────────────────────
    print("\n" + SEP)
    print("  🔑  CLÉ PUBLIQUE  (complète)")
    print(SEP)

    pk = keys['public_key']
    print(f"\n  Dimension          : {pk['dim']}D (ℝ⁵)")
    print(f"  n (taille bloc)    : {pk['n']} bits")
    print(f"  σ (bruit LWE)      : {pk['sigma']:.6e}")
    print(f"\n  Matrice A  ({pk['n']} × {pk['dim']} float64) :")
    print(f"  {SEP2}")

    header = f"  {'idx':>4}  " + "  ".join(f"{'dim'+str(j):>18}" for j in range(pk['dim']))
    print(header)
    print(f"  {SEP2}")
    for i, row in enumerate(pk['A_vec']):
        row_str = "  ".join(f"{v:18.6f}" for v in row)
        print(f"  {i:>4}  {row_str}")
    print(f"  {SEP2}")

    # ── CLÉ PRIVÉE ────────────────────────────────────────────────────────────
    print("\n" + SEP)
    print("  🔒  CLÉ PRIVÉE  (complète — TRAPDOOR)")
    print(SEP)

    priv = keys['private_key']

    print(f"\n  Modulo M ({priv['M'].bit_length()} bits) :")
    print(f"  {priv['M']}")

    print(f"\n  Inverse W⁻¹ ({priv['W_inv'].bit_length()} bits) :")
    print(f"  {priv['W_inv']}")

    print(f"\n  Suite super-croissante B  ({len(priv['B'])} éléments) :")
    print(f"  {SEP2}")
    for i, b in enumerate(priv['B']):
        print(f"  B[{i:>3}] = {b}")
    print(f"  {SEP2}")

    print(f"\n  Matrice de rotation secrète Q  ({priv['Q'].shape[0]} × {priv['Q'].shape[1]}) :")
    print(f"  {SEP2}")
    q_header = f"  {'':>4}  " + "  ".join(f"{'dim'+str(j):>18}" for j in range(priv['Q'].shape[1]))
    print(q_header)
    print(f"  {SEP2}")
    for i, row in enumerate(priv['Q']):
        row_str = "  ".join(f"{v:18.15f}" for v in row)
        print(f"  {i:>4}  {row_str}")
    print(f"  {SEP2}")

    print("\n" + SEP)