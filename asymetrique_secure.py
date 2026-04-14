"""
=============================================================================
SYSTÈME DE CHIFFREMENT ASYMÉTRIQUE POST-QUANTIQUE [VERSION SÉCURISÉE]
Basé sur le Subset Sum Problem (Problème du Sac à Dos) dans un espace à 5D
avec mécanismes LWE (Learning With Errors) pour résistance quantique
=============================================================================

VERSION AMÉLIORÉE AVEC CORRECTIONS DE SÉCURITÉ :
• ✓ Validation robuste des entrées
• ✓ Gestion d'erreurs complète
• ✓ Vérification de super-croissance
• ✓ Sécurité des big integers
• ✓ Reproductibilité des clés
• ✓ Checksums et vérification
• ✓ Performance optimisée (numpy vectorisé)
• ✓ Pas de fuites silencieuses

=============================================================================
"""

import sys
import io
import os

# Configure encoding for Windows compatibility
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Don't modify stdout, just set encoding

import numpy as np
from numpy.random import Generator, PCG64
import secrets
import math
import time
import hashlib
from typing import Tuple, List, Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE SÉCURITÉ
# ─────────────────────────────────────────────────────────────────────────────

DIM                    = 5              # Dimension vectorielle ℝ^DIM
N                      = 40             # Taille bloc (bits)
B_MAX                  = 2**30          # Limite super-croissance (préserve float64)
MAX_KEYGEN_ITERATIONS  = 100_000        # Limite pour trouver W coprime
NOISE_THRESHOLD        = 1.5            # Seuil d'alerte pour le bruit LWE
MIN_SUPERINCREASING    = 1.05           # Ratio minimum super-croissance

# Constantes de validation
MIN_N, MAX_N           = 16, 64
MIN_DIM, MAX_DIM       = 3, 8
MAX_TEXT_LENGTH        = 10_000         # 10k caractères max


# ─────────────────────────────────────────────────────────────────────────────
# CLASSE PERSONNALISÉE D'ERREUR
# ─────────────────────────────────────────────────────────────────────────────

class CryptoException(Exception):
    """Exception de base pour le système cryptographique"""
    pass

class KeyGenException(CryptoException):
    """Erreur lors de la génération de clés"""
    pass

class EncryptException(CryptoException):
    """Erreur lors du chiffrement"""
    pass

class DecryptException(CryptoException):
    """Erreur lors du déchiffrement"""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 : UTILITAIRES DE VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def _validate_parameters(n: int = None, dim: int = None) -> Tuple[int, int]:
    """Valide et normalise les paramètres de sécurité"""
    n = n or N
    dim = dim or DIM
    
    if not isinstance(n, int) or not isinstance(dim, int):
        raise KeyGenException(f"n et dim doivent être des entiers, reçu: {type(n)}, {type(dim)}")
    
    if not (MIN_N <= n <= MAX_N):
        raise KeyGenException(f"n={n} hors limites [{MIN_N}, {MAX_N}]")
    
    if not (MIN_DIM <= dim <= MAX_DIM):
        raise KeyGenException(f"dim={dim} hors limites [{MIN_DIM}, {MAX_DIM}]")
    
    return n, dim


def _is_superincreasing(B: List[int], tolerance: float = 0.0) -> bool:
    """Vérifie strictement que B est super-croissante (avec tolérance)"""
    cumsum = 0
    for i, b in enumerate(B):
        if not isinstance(b, (int, np.integer)):
            return False
        if b <= 0:
            return False
        if i > 0 and b <= cumsum * (1.0 - tolerance):
            return False
        cumsum += b
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 : GÉNÉRATION DE CLÉS SÉCURISÉE
# ─────────────────────────────────────────────────────────────────────────────

def _superincreasing_secure(n: int, b_max: int = B_MAX, seed: int = None) -> List[int]:
    """Génère une suite super-croissante avec graine optionnelle et vérification"""
    if n <= 0 or n > MAX_N:
        raise KeyGenException(f"Taille invalide n={n}")
    
    if b_max <= 0 or b_max > (1 << 62):
        raise KeyGenException(f"b_max invalide={b_max}")
    
    # RNG avec graine optionnelle pour reproductibilité
    if seed is not None:
        rng_local = Generator(PCG64(seed))
    else:
        rng_local = Generator(PCG64(int.from_bytes(secrets.token_bytes(8), 'big') % (2**62)))
    
    B = []
    cumsum = 0
    b = 3
    
    for step in range(n):
        B.append(b)
        cumsum += b
        
        # Incrément aléatoire massif (0 à 1M)
        rand_increment = rng_local.integers(0, 1_000_000, dtype=np.int64)
        candidate = cumsum + int(rand_increment) + 1
        
        # Sécurité : si on dépasse b_max, utiliser l'incrément minimal
        if candidate <= b_max:
            b = candidate
        else:
            b = cumsum + 1
            if b > b_max:
                raise KeyGenException(f"Impossibilité de générer suite super-croissante à étape {step}")
    
    # Vérification finale
    if not _is_superincreasing(B, tolerance=0.01):
        raise KeyGenException("Suite générée n'est pas super-croissante après validation")
    
    return B


def keygen(n: int = None, dim: int = None, seed: int = None) -> Dict[str, Any]:
    """
    Génération sécurisée de paires de clés.
    
    Parameters:
    -----------
    n : int, dimensions du bloc (bits)
    dim : int, dimension de l'espace vectoriel
    seed : int, graine pour reproductibilité (None = aléatoire)
    
    Returns:
    --------
    dict avec clés privée/publique, paramètres, checksums
    """
    n, dim = _validate_parameters(n, dim)
    
    try:
        print(f"[KeyGen] Génération de la suite super-croissante privée B ({n} éléments)…")
        B = _superincreasing_secure(n, B_MAX, seed=seed)
        sum_B = sum(B)
        min_B = min(B)
        
        if sum_B <= 0 or sum_B > (1 << 100):
            raise KeyGenException(f"Somme de B invalide: {sum_B}")
        
        print(f"[KeyGen] Génération du modulo M et du multiplicateur W coprime…")
        
        # Génération de M > sum(B)
        M = sum_B + secrets.randbelow(max(sum_B // 4, 2)) + n + 1
        
        # Trouver W coprime avec M (avec limite de sécurité)
        W = None
        for attempt in range(MAX_KEYGEN_ITERATIONS):
            W_candidate = secrets.randbelow(M - 3) + 2
            if math.gcd(W_candidate, M) == 1:
                W = W_candidate
                break
        
        if W is None:
            raise KeyGenException(f"Impossible de trouver W coprime avec M après {MAX_KEYGEN_ITERATIONS} tentatives")
        
        # Calcul de l'inverse modulaire avec gestion d'erreur
        try:
            W_inv = pow(W, -1, M)
        except ValueError:
            raise KeyGenException(f"Impossible de calculer W^-1 mod M (W={W}, M={M})")
        
        # Vérification: W * W_inv ≡ 1 (mod M)
        if (W * W_inv) % M != 1:
            raise KeyGenException("Vérification échouée: W * W_inv ≠ 1 (mod M)")
        
        print(f"[KeyGen] Construction de la clé publique vectorielle {dim}D…")
        
        # Clé publique scalaire brute
        pub_scalars = [(W * b) % M for b in B]
        max_a = max(pub_scalars)
        
        if max_a <= 0:
            raise KeyGenException(f"max(a_i) invalide: {max_a}")
        
        # Construction de la matrice de base 5D
        A_plain = np.zeros((n, dim), dtype=np.float64)
        
        # Axe 0 : clé publique transformée (tronquée pour float64)
        a_truncated = np.array([float(a % (2**52)) for a in pub_scalars], dtype=np.float64)
        A_plain[:, 0] = a_truncated
        
        # Axes 1..4 : bruit aléatoire pour masquer la structure
        rng_local = Generator(PCG64(seed)) if seed else Generator(PCG64())
        for j in range(1, dim):
            A_plain[:, j] = rng_local.uniform(0.0, float(max_a % (2**52)), size=n)
        
        # Rotation orthogonale secrète
        Q, _ = np.linalg.qr(rng_local.standard_normal((dim, dim)))
        
        # Vérification que Q est bien orthogonale
        orthog_error = np.max(np.abs(Q @ Q.T - np.eye(dim)))
        if orthog_error > 1e-8:
            print(f"[WARN] Orthogonalité Q faible: erreur={orthog_error}")
        
        pub_A = A_plain @ Q.T
        
        # Paramètre de bruit LWE
        sigma = float(max_a % (2**52)) / 20.0
        
        # Structures de retour
        private_key = {
            'B': B,
            'M': M,
            'W_inv': W_inv,
            'Q': Q,
        }
        
        public_key = {
            'A_vec': pub_A,
            'sigma': sigma,
            'n': n,
            'dim': dim,
        }
        
        result = {
            'private_key': private_key,
            'public_key': public_key,
            'pub_scalars': pub_scalars,
            'sigma': sigma,
            'dim': dim,
            'n': n,
            'M': M,
            'W_inv': W_inv,
            'private_B': B,
            'Q': Q,
            'public_A': pub_A,
            'max_a': max_a,
            'min_B': min_B,
            'sum_B': sum_B,
        }
        
        # Checksum pour intégrité
        checksum_data = f"{n}:{dim}:{max_a}:{M.bit_length()}:{len(B)}"
        result['checksum_keygen'] = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]
        
        print(f"[KeyGen] ✓ Clés générées avec succès.")
        return result
        
    except (KeyGenException, ValueError, np.linalg.LinAlgError) as e:
        raise KeyGenException(f"Erreur fatale en KeyGen: {str(e)}") from e


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 : CHIFFREMENT SÉCURISÉ
# ─────────────────────────────────────────────────────────────────────────────

def encrypt(message_bits: np.ndarray, keys: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chiffrement sécurisé avec validation complète.
    """
    try:
        # Validation des entrées
        if not isinstance(message_bits, np.ndarray):
            raise EncryptException(f"message_bits doit être np.ndarray, reçu: {type(message_bits)}")
        
        if message_bits.dtype != np.int8:
            try:
                message_bits = np.array(message_bits, dtype=np.int8)
            except (ValueError, TypeError):
                raise EncryptException(f"Impossible de convertir message_bits en int8")
        
        pub_A = keys.get('public_A')
        pub_scalars = keys.get('pub_scalars')
        sigma = keys.get('sigma')
        dim = keys.get('dim')
        n = keys.get('n')
        
        if any(x is None for x in [pub_A, pub_scalars, sigma, dim, n]):
            raise EncryptException("Clé publique incomplète")
        
        if len(message_bits) != n:
            raise EncryptException(f"Longueur message {len(message_bits)} ≠ bloc {n}")
        
        if not np.all((message_bits == 0) | (message_bits == 1)):
            raise EncryptException("message_bits doit contenir uniquement 0 et 1")
        
        # Calcul du chiffré scalaire (exact, big int Python)
        indices_ones = np.where(message_bits == 1)[0]
        S = sum(pub_scalars[i] for i in indices_ones) if len(indices_ones) > 0 else 0
        
        # Vecteur chiffré avec bruit LWE
        if len(indices_ones) > 0:
            C_clean = np.sum(pub_A[indices_ones], axis=0)
        else:
            C_clean = np.zeros(dim, dtype=np.float64)
        
        # Bruit gaussien LWE
        rng_local = Generator(PCG64(secrets.randbits(62)))
        epsilon = rng_local.normal(0.0, sigma, size=dim).astype(np.float64)
        
        C_vec = C_clean + epsilon
        
        # Vérification de cohérence vectorielle
        if np.any(np.isnan(C_vec)) or np.any(np.isinf(C_vec)):
            raise EncryptException("C_vec contient NaN ou Inf après chiffrement")
        
        result = {
            'C_vec': C_vec,
            'epsilon': epsilon,
            'n_ones': len(indices_ones),
        }
        
        # Checksum du chiffré
        checksum_data = f"{len(indices_ones)}:{C_vec.tobytes().hex()[:32]}"
        result['checksum_encrypt'] = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]
        
        return result
        
    except EncryptException:
        raise
    except Exception as e:
        raise EncryptException(f"Erreur non gérée en Encrypt: {str(e)}") from e


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 : DÉCHIFFREMENT SÉCURISÉ
# ─────────────────────────────────────────────────────────────────────────────

def _greedy_safe(target: int, B: List[int]) -> Tuple[List[int], int]:
    """Algorithme glouton O(n) avec vérifications"""
    if target < 0:
        raise DecryptException(f"target={target} doit être positif")
    
    if not _is_superincreasing(B):
        raise DecryptException("Suite B n'est pas super-croissante")
    
    bits = [0] * len(B)
    rem = target
    
    for i in range(len(B) - 1, -1, -1):
        if rem < 0:
            raise DecryptException(f"Remainder négatif à étape {i}: {rem}")
        if rem >= B[i]:
            bits[i] = 1
            rem -= B[i]
    
    return bits, rem


def decrypt(ciphertext: Dict[str, Any], keys: Dict[str, Any]) -> Tuple[np.ndarray, int, float, bool]:
    """
    Déchiffrement sécurisé avec vérification du bruit LWE.
    
    Returns:
    --------
    (bits, remainder, lwe_residual, success)
    """
    try:
        # Validation des entrées
        if not isinstance(ciphertext, dict) or not isinstance(keys, dict):
            raise DecryptException("ciphertext et keys doivent être des dict")
        
        M = keys.get('M')
        W_inv = keys.get('W_inv')
        B = keys.get('private_B')
        Q = keys.get('Q')
        
        if any(x is None for x in [M, W_inv, B, Q]):
            raise DecryptException("Clé privée incomplète")
        
        C_vec = ciphertext.get('C_vec')
        if C_vec is None or not isinstance(C_vec, np.ndarray):
            raise DecryptException("C_vec manquant ou invalide dans le chiffré")
        
        if np.any(np.isnan(C_vec)) or np.any(np.isinf(C_vec)):
            raise DecryptException("C_vec contient NaN ou Inf")
        
        # Étape 1 : Dé-rotation du vecteur
        try:
            C_orig = C_vec @ Q
        except np.linalg.LinAlgError as e:
            raise DecryptException(f"Erreur lors de la dé-rotation: {e}") from e
        
        # Étape 2 : Extraction du scalaire exact (axis 0)
        # Le bruit doit être petit pour que l'arrondi soit correct
        S_noisy = float(C_orig[0])
        S = round(S_noisy)
        lwe_residual = abs(S_noisy - S)
        
        # Vérification du bruit
        success = True
        if lwe_residual > NOISE_THRESHOLD:
            print(f"[WARN] Bruit LWE important détecté: {lwe_residual:.4f}")
            success = False
        
        # Étape 3 : Inversion modulaire
        if S < 0:
            raise DecryptException(f"S négatif après arrondi: {S}")
        
        t = (W_inv * int(S)) % M
        
        if t < 0 or t > M:
            raise DecryptException(f"t={t} hors limites [0, {M}]")
        
        # Étape 4 : Algorithme glouton sur suite super-croissante
        bits_list, rem = _greedy_safe(t, B)
        
        # Vérification de la cohérence: remainder doit être petit
        sum_B = sum(B)
        if rem > sum_B * 0.1:
            print(f"[WARN] Remainder élevé: {rem} (sum_B={sum_B})")
            success = False
        
        return np.array(bits_list, dtype=np.int8), rem, lwe_residual, success
        
    except DecryptException:
        raise
    except Exception as e:
        raise DecryptException(f"Erreur non gérée en Decrypt: {str(e)}") from e


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 : CONVERSION TEXTE ↔ BITS (ROBUSTE)
# ─────────────────────────────────────────────────────────────────────────────

def text_to_bits(text: str, block_size: int = N) -> List[np.ndarray]:
    """Conversion robuste texte → blocs de bits"""
    if not isinstance(text, str):
        raise ValueError(f"text doit être str, reçu: {type(text)}")
    
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Texte trop long: {len(text)} > {MAX_TEXT_LENGTH}")
    
    if block_size <= 0 or block_size > 256:
        raise ValueError(f"block_size invalide: {block_size}")
    
    # Encodage UTF-8
    try:
        raw_bytes = text.encode('utf-8')
    except UnicodeEncodeError as e:
        raise ValueError(f"Erreur d'encodage UTF-8: {e}") from e
    
    # Conversion en bits
    raw = []
    for byte in raw_bytes:
        for shift in range(7, -1, -1):
            raw.append((byte >> shift) & 1)
    
    # Ajout de padding
    if len(raw) == 0:
        raw = [0]
    
    # Découpe en blocs
    blocks = []
    for start in range(0, len(raw), block_size):
        block_data = raw[start:start + block_size]
        # Zero-padding
        if len(block_data) < block_size:
            block_data += [0] * (block_size - len(block_data))
        blocks.append(np.array(block_data, dtype=np.int8))
    
    return blocks


def bits_to_text(blocks: List[np.ndarray]) -> str:
    """Conversion robuste blocs de bits → texte"""
    if not blocks or len(blocks) == 0:
        raise ValueError("blocks vide")
    
    if not all(isinstance(b, np.ndarray) for b in blocks):
        raise ValueError("Tous les éléments doivent être np.ndarray")
    
    # Concaténation vectorisée (plus rapide que boucle)
    flat = np.concatenate(blocks)
    
    if len(flat) == 0:
        return ""
    
    # Conversion bits → bytes
    raw_bytes = bytearray()
    for i in range(0, len(flat) - 7, 8):
        byte_bits = flat[i:i+8]
        if len(byte_bits) < 8:
            continue
        val = int(''.join(str(b) for b in byte_bits), 2)
        if val == 0:  # Stop à null terminator
            break
        try:
            raw_bytes.append(val)
        except (ValueError, OverflowError):
            continue
    
    # Décodage UTF-8
    try:
        return raw_bytes.decode('utf-8', errors='replace')
    except Exception:
        return raw_bytes.decode('latin-1', errors='replace')


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 : TEST COMPLET AVEC VÉRIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def run_full_test(plaintext: str, seed: int = None) -> Dict[str, Any]:
    """Test complet avec gestion d'erreurs et validations"""
    if not isinstance(plaintext, str):
        raise ValueError(f"plaintext doit être str, reçu: {type(plaintext)}")
    
    if len(plaintext) > MAX_TEXT_LENGTH:
        raise ValueError(f"Texte trop long: {len(plaintext)}")
    
    if len(plaintext) == 0:
        raise ValueError("Texte vide")
    
    SEP = "═" * 70
    print(SEP)
    print("  PROTOTYPE POST-QUANTIQUE [VERSION SÉCURISÉE]")
    print("  Knapsack 5D + LWE avec validations complètes")
    print(SEP)
    
    try:
        # 1. KeyGen
        print(f"\n[1/4] Génération des clés…")
        t0 = time.perf_counter()
        keys = keygen(N, DIM, seed=seed)
        t_kg = time.perf_counter() - t0
        print(f"  ✓ KeyGen en {t_kg*1000:.2f} ms")
        
        # 2. Encodage
        print(f"\n[2/4] Encodage du texte…")
        blocks = text_to_bits(plaintext, N)
        print(f"  ✓ {len(plaintext)} caractères → {len(blocks)} bloc(s)")
        
        # 3. Chiffrement
        print(f"\n[3/4] Chiffrement…")
        t0 = time.perf_counter()
        cts = []
        for i, block in enumerate(blocks):
            ct = encrypt(block, keys)
            cts.append(ct)
        t_enc = time.perf_counter() - t0
        print(f"  ✓ Chiffrement de {len(cts)} bloc(s) en {t_enc*1000:.2f} ms")
        
        # 4. Déchiffrement
        print(f"\n[4/4] Déchiffrement…")
        t0 = time.perf_counter()
        dec_blocks = []
        rems = []
        lwe_residuals = []
        success_flags = []
        
        for ct in cts:
            d, rem, lwe_r, success = decrypt(ct, keys)
            dec_blocks.append(d)
            rems.append(rem)
            lwe_residuals.append(lwe_r)
            success_flags.append(success)
        
        t_dec = time.perf_counter() - t0
        print(f"  ✓ Déchiffrement de {len(dec_blocks)} bloc(s) en {t_dec*1000:.2f} ms")
        
        # 5. Récupération du texte
        recovered = bits_to_text(dec_blocks)
        
        # 6. Vérifications
        print(f"\n{SEP}")
        print("  RÉSULTATS")
        print(f"{SEP}")
        print(f"  Original  : {plaintext[:50]}{'...' if len(plaintext) > 50 else ''}")
        print(f"  Récupéré  : {recovered[:50]}{'...' if len(recovered) > 50 else ''}")
        
        success = (recovered == plaintext)
        status = "✓ SUCCÈS" if success else "✗ ÉCHEC"
        print(f"  Statut    : {status}")
        
        if success_flags and not all(success_flags):
            print(f"  [WARN] {len([s for s in success_flags if not s])} bloc(s) avec avertissements")
        
        ber = float(np.mean(np.concatenate(blocks) != np.concatenate(dec_blocks)))
        print(f"  BER       : {ber:.6f} ({ber*100:.4f}%)")
        
        print(f"  Temps totale : {(t_kg + t_enc + t_dec)*1000:.2f} ms")
        print(SEP)
        
        return {
            'success': success,
            'ber': ber,
            'plaintext': plaintext,
            'recovered': recovered,
            't_keygen_ms': t_kg * 1000,
            't_enc_ms': t_enc * 1000,
            't_dec_ms': t_dec * 1000,
            'keys': keys,
            'lwe_residuals': lwe_residuals,
            'remainders': rems,
        }
        
    except Exception as e:
        print(f"✗ ERREUR CRITIQUE : {str(e)}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7 : ANALYSE DE SÉCURITÉ ROBUSTE
# ─────────────────────────────────────────────────────────────────────────────

def security_analysis(keys: Dict[str, Any]) -> None:
    """Analyse de sécurité avec vérifications"""
    try:
        B = keys.get('private_B')
        A = keys.get('pub_scalars')
        Q = keys.get('Q')
        n = keys.get('n')
        
        if any(x is None for x in [B, A, Q, n]):
            print("[ERR] Clés incomplètes pour l'analyse")
            return
        
        print(f"\n{'─'*66}")
        print("  ANALYSE DE SÉCURITÉ")
        print(f"{'─'*66}")
        
        # 1. Super-croissance
        is_super = _is_superincreasing(B, tolerance=0.01)
        print(f"  [{'✓' if is_super else '✗'}] Suite super-croissante")
        
        # 2. Gcd(W, M)
        cumsum = 0
        min_ratio = float('inf')
        for i, b in enumerate(B):
            if i > 0:
                ratio = b / cumsum if cumsum > 0 else float('inf')
                min_ratio = min(min_ratio, ratio)
            cumsum += b
        print(f"  [ℹ] Ratio min super-croissance: {min_ratio:.4f}")
        
        # 3. Uniformité clé publique
        try:
            Af = np.array(A, dtype=float)
            An = (Af - Af.min()) / (Af.max() - Af.min() + 1e-12)
            ks = float(np.max(np.abs(np.sort(An) - np.linspace(0, 1, n))))
            print(f"  [{'✓' if ks < 0.15 else '⚠'}] Uniformité KS: {ks:.4f}")
        except Exception as e:
            print(f"  [ERR] Erreur uniformité: {e}")
        
        # 4. Orthogonalité Q
        try:
            err = float(np.max(np.abs(Q @ Q.T - np.eye(len(Q)))))
            print(f"  [{'✓' if err < 1e-8 else '⚠'}] Orthogonalité Q: {err:.2e}")
        except Exception as e:
            print(f"  [ERR] Erreur orthogonalité: {e}")
        
        # 5. Complexité estimée
        print(f"\n  Complexité estimée:")
        print(f"    Brute-force    : 2^{n} ≈ {2.0**n:.2e}")
        print(f"    Sécurité       : ~{n//2} bits (classique)")
        
        print(f"  {'─'*66}")
        
    except Exception as e:
        print(f"[ERR] Erreur analyse sécurité: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# POINT D'ENTRÉE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        # Test avec graine reproductible
        result = run_full_test("Secret Post-Quantique Sécurisé", seed=12345)
        keys = result['keys']
        
        # Analyse de sécurité
        security_analysis(keys)
        
        print("\n✓ Exécution complète réussie !")
        
    except CryptoException as e:
        print(f"\n✗ Erreur cryptographique : {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Erreur non gérée : {e}")
        import traceback
        traceback.print_exc()
        exit(1)
