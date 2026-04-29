import hashlib
import hmac
import struct

TAILLE_BLOC = 16
MAGIC = b'CDX2'
VERSION = 1
NB_TOURS = 10

# ═══════════════════════════════════════════
# LCG
# ═══════════════════════════════════════════
def lcg(seed):
    return (seed * 1664525 + 1013904223) % (2**32)

# ═══════════════════════════════════════════
# CONSTRUCTION DES STRUCTURES DEPUIS UN SEED
# ═══════════════════════════════════════════
def build_sbox_from_seed(seed):
    sbox = list(range(256))
    s = seed
    for i in range(255, 0, -1):
        s = lcg(s)
        j = s % (i + 1)
        sbox[i], sbox[j] = sbox[j], sbox[i]
    return sbox

def inverser_sbox(sbox):
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    return inv

def build_perm_from_seed(seed):
    perm = list(range(128))
    s = seed
    for i in range(127, 0, -1):
        s = lcg(s)
        j = s % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    inv_perm = [0] * 128
    for i, v in enumerate(perm):
        inv_perm[v] = i
    return perm, inv_perm

def build_subkey_from_seed(seed):
    s = seed
    sk = []
    for _ in range(TAILLE_BLOC):
        s = lcg(s)
        sk.append(s % 256)
    return sk

def construire_contexte_depuis_seed(S):
    seed_SA   = (31 * S) % (2**32)
    seed_SB   = (61 * S) % (2**32)
    seed_perm = (97 * S) % (2**32)

    SA = build_sbox_from_seed(seed_SA)
    SB = build_sbox_from_seed(seed_SB)
    perm, inv_perm = build_perm_from_seed(seed_perm)

    sous_cles = []
    for r in range(NB_TOURS):
        seed_sk = (31 * (r + 1) * S) % (2**32)
        sous_cles.append(build_subkey_from_seed(seed_sk))

    return {
        'sa'      : SA,
        'sa_inv'  : inverser_sbox(SA),
        'sb'      : SB,
        'sb_inv'  : inverser_sbox(SB),
        'perm'    : perm,
        'ip'      : inv_perm,
        'sous_cles': sous_cles
    }

# ═══════════════════════════════════════════
# OPÉRATIONS DE BASE
# ═══════════════════════════════════════════
def xor_blocs(a, b):
    return [a[i] ^ b[i] for i in range(TAILLE_BLOC)]

def vortex_inv(bloc, sk):
    result = bloc[:]
    for i in range(TAILLE_BLOC):
        rotation = sk[i] % 8
        result[i] = ((bloc[i] >> rotation) | (bloc[i] << (8 - rotation))) & 0xFF
    return result

def permutation_inv(bloc, inv_perm):
    bits_in = []
    for octet in bloc:
        for bit in range(7, -1, -1):
            bits_in.append((octet >> bit) & 1)
    bits_out = [0] * 128
    for i in range(128):
        bits_out[inv_perm[i]] = bits_in[i]
    result = []
    for i in range(0, 128, 8):
        octet = 0
        for bit in range(8):
            octet = (octet << 1) | bits_out[i + bit]
        result.append(octet)
    return result

# ═══════════════════════════════════════════
# DÉCHIFFREMENT D'UN BLOC
# ═══════════════════════════════════════════
def dechiffrer_bloc(bloc, ctx):
    b = bloc[:]
    for r in range(NB_TOURS - 1, -1, -1):
        sk = ctx['sous_cles'][r]
        b = permutation_inv(b, ctx['ip'])
        b = [ctx['sb_inv'][x] for x in b]
        b = vortex_inv(b, sk)
        b = [ctx['sa_inv'][x] for x in b]
        b = xor_blocs(b, sk)
    return b

# ═══════════════════════════════════════════
# PARSING DU MESSAGE CHIFFRÉ
# ═══════════════════════════════════════════
def parser_message(data):
    offset = 0
    magic   = data[offset:offset+4];  offset += 4
    version = data[offset];           offset += 1
    sel     = data[offset:offset+16]; offset += 16
    iv      = data[offset:offset+16]; offset += 16
    # Le tag HMAC est les 16 derniers octets
    tag        = data[-16:]
    ciphertext = data[offset:-16]
    return magic, version, sel, iv, ciphertext, tag

# ═══════════════════════════════════════════
# ATTAQUE BRUTE FORCE SUR S (32 bits)
# ═══════════════════════════════════════════
def attaque_brute_force(hex_cible):
    data = bytes.fromhex(hex_cible)
    magic, version, sel, iv, ciphertext, tag = parser_message(data)

    # Vérification basique du magic
    if magic != MAGIC:
        print("[-] Magic invalide, ce n'est pas un message CODEX.")
        return None

    # Découpage en blocs
    blocs_chiffres = [list(ciphertext[i:i+TAILLE_BLOC])
                      for i in range(0, len(ciphertext), TAILLE_BLOC)]

    nb_blocs = len(blocs_chiffres)
    print(f"[*] Démarrage brute force sur 2^32 seeds...")
    print(f"[*] {nb_blocs} blocs à déchiffrer")

    dernier_bloc_c = blocs_chiffres[-1]

    # ✅ FIX : si 1 seul bloc, le "précédent" est l'IV (définition CBC)
    if nb_blocs == 1:
        avant_dernier_bloc_c = list(iv)
    else:
        avant_dernier_bloc_c = blocs_chiffres[-2]

    for S in range(2**32):
        ctx = construire_contexte_depuis_seed(S)
        bloc_dec  = dechiffrer_bloc(dernier_bloc_c, ctx)
        bloc_xore = xor_blocs(bloc_dec, avant_dernier_bloc_c)

        pad = bloc_xore[-1]
        if 1 <= pad <= 16 and all(bloc_xore[-(i+1)] == pad for i in range(pad)):
            # Padding valide → déchiffrer tous les blocs
            print(f"[+] Seed trouvé : S = {S}")
            print(f"[+] Padding valide : 0x{pad:02X} × {pad}")

            plaintext_blocs = []
            prev = list(iv)
            for bloc_c in blocs_chiffres:
                dec = dechiffrer_bloc(bloc_c, ctx)
                plain = xor_blocs(dec, prev)
                plaintext_blocs.append(plain)
                prev = bloc_c

            # Retirer le padding
            tous = []
            for b in plaintext_blocs:
                tous.extend(b)
            tous = tous[:-pad]

            try:
                message = bytes(tous).decode('utf-8')
                print(f"[+] Message déchiffré : {message}")
                return message
            except UnicodeDecodeError:
                # Faux positif, on continue
                continue

    print("[-] Aucun seed trouvé.")
    return None

# ═══════════════════════════════════════════
# POINT D'ENTRÉE
# ═══════════════════════════════════════════
if __name__ == "__main__":
    hex_cible = input("Colle le message chiffré (hex) : ").strip()
    resultat  = attaque_brute_force(hex_cible)