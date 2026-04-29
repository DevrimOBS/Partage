import tkinter as tk
from tkinter import messagebox
import secrets
import hashlib
import hmac
import re

TAILLE_BLOC = 16
NB_TOURS = 10
MAGIC = b"CDX2"
VERSION = 1
MAX_MSG = 4096
MIN_CLÉ = 64

regex_hex = re.compile(r'^[0-9a-fA-F]+$')

def lcg(seed):
    return (seed * 1664525 + 1013904223) % (2**32)

def effacer_buffer(buf):
    for i in range(len(buf)):
        buf[i] = 0

def comparer_hmac(a, b):
    return hmac.compare_digest(a, b)

def deriver_cle(password, sel):
    cle = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        sel,
        120000,
        dklen=32
    )
    return cle

def separer_cles(cle_master):
    cle_chiffrement = cle_master[:16]
    cle_hmac = cle_master[16:]
    return cle_chiffrement, cle_hmac

def preparer_cle(kb):
    d = [0] * 16
    for i in range(len(kb)):
        b = kb[i]
        d[i % 16] = d[i % 16] ^ ((b * (i + 1)) % 256)
    return d

def gen_sbox(cle, sm=31):
    table = list(range(256))
    seed = 0
    for i in range(len(cle)):
        seed += cle[i] * (i + 1) * sm
    seed = seed % (2**32)
    for i in range(255, 0, -1):
        seed = lcg(seed)
        j = seed % (i + 1)
        temp = table[i]
        table[i] = table[j]
        table[j] = temp
    return table

def inverser_sbox(s):
    inv = [0] * 256
    for i in range(256):
        inv[s[i]] = i
    return inv

def gen_permutation(cle, n=128):
    p = list(range(n))
    seed = 0
    for i in range(len(cle)):
        seed += cle[i] * (i + 1) * 97
    seed = seed % (2**32)
    for i in range(n - 1, 0, -1):
        seed = lcg(seed)
        j = seed % (i + 1)
        p[i], p[j] = p[j], p[i]
    ip = [0] * n
    for i in range(n):
        ip[p[i]] = i
    return p, ip

def gen_sous_cle(cle, tour):
    seed = 0
    for i in range(len(cle)):
        seed += cle[i] * (i + 1) * 31 * (tour + 1)
    seed = seed % (2**32)
    rk = []
    for _ in range(16):
        seed = lcg(seed)
        rk.append(seed % 256)
    return rk

def bloc_en_bits(bl):
    bits = []
    for b in bl:
        for i in range(7, -1, -1):
            bits.append((b >> i) & 1)
    return bits

def bits_en_bloc(bits):
    r = []
    for i in range(0, len(bits), 8):
        b = 0
        for j in range(8):
            b = (b << 1) | bits[i + j]
        r.append(b)
    return r

def appliquer_permutation(bl, p):
    bits = bloc_en_bits(bl)
    nouveaux_bits = [0] * len(bits)
    for i in range(len(bits)):
        nouveaux_bits[p[i]] = bits[i]
    return bits_en_bloc(nouveaux_bits)

def appliquer_sbox(b, s):
    res = []
    for x in b:
        res.append(s[x])
    return res

def xor_blocs(a, b):
    res = []
    for i in range(TAILLE_BLOC):
        res.append(a[i] ^ b[i])
    return res

def rotation_gauche(b, n):
    n = n % 8
    return ((b << n) | (b >> (8 - n))) & 0xFF

def rotation_droite(b, n):
    n = n % 8
    return ((b >> n) | (b << (8 - n))) & 0xFF

def vortex(b, rk):
    res = []
    for i in range(TAILLE_BLOC):
        res.append(rotation_gauche(b[i], rk[i] & 7))
    return res

def vortex_inverse(b, rk):
    res = []
    for i in range(TAILLE_BLOC):
        res.append(rotation_droite(b[i], rk[i] & 7))
    return res

def creer_contexte(cle_bytes):
    sa = gen_sbox(cle_bytes, 31)
    sb = gen_sbox(cle_bytes, 61)
    sa_inv = inverser_sbox(sa)
    sb_inv = inverser_sbox(sb)
    p, ip = gen_permutation(cle_bytes)
    sous_cles = []
    for r in range(NB_TOURS):
        sous_cles.append(gen_sous_cle(cle_bytes, r))
    return {
        'sa': sa, 'sb': sb,
        'sa_inv': sa_inv, 'sb_inv': sb_inv,
        'p': p, 'ip': ip,
        'sous_cles': sous_cles
    }

def chiffrer_bloc(pt, ctx):
    b = list(pt)
    for r in range(NB_TOURS):
        rk = ctx['sous_cles'][r]
        b = xor_blocs(b, rk)
        b = appliquer_sbox(b, ctx['sa'])
        b = vortex(b, rk)
        b = appliquer_sbox(b, ctx['sb'])
        b = appliquer_permutation(b, ctx['p'])
    return b

def dechiffrer_bloc(ct, ctx):
    b = list(ct)
    for r in range(NB_TOURS - 1, -1, -1):
        rk = ctx['sous_cles'][r]
        b = appliquer_permutation(b, ctx['ip'])
        b = appliquer_sbox(b, ctx['sb_inv'])
        b = vortex_inverse(b, rk)
        b = appliquer_sbox(b, ctx['sa_inv'])
        b = xor_blocs(b, rk)
    return b

def ajouter_padding(data):
    n = TAILLE_BLOC - (len(data) % TAILLE_BLOC)
    return data + [n] * n

def enlever_padding(data):
    if not data or len(data) % TAILLE_BLOC != 0:
        raise ValueError("Le padding est invalide")
    n = data[-1]
    if n < 1 or n > TAILLE_BLOC:
        raise ValueError("Le padding est invalide")
    for i in range(n):
        if data[-(i + 1)] != n:
            raise ValueError("Le padding est invalide")
    return data[:-n]

def verifier_solidite_cle(mdp):
    if len(mdp) < MIN_CLÉ:
        return False, f"La cle doit faire au moins {MIN_CLÉ} caracteres !"
    a_minuscule = False
    a_majuscule = False
    a_chiffre = False
    a_symbole = False
    for c in mdp:
        if c.islower():
            a_minuscule = True
        elif c.isupper():
            a_majuscule = True
        elif c.isdigit():
            a_chiffre = True
        else:
            a_symbole = True
    score = 0
    if a_minuscule: score += 1
    if a_majuscule: score += 1
    if a_chiffre: score += 1
    if a_symbole: score += 1
    if score < 3:
        return False, "Mets des majuscules, minuscules et chiffres au moins !"
    return True, "OK"

def verifier_format_hex(hex_str):
    if not hex_str:
        return False, "Le champ est vide."
    if len(hex_str) % 2 != 0:
        return False, "Format hex invalide (longueur impaire)."
    if not regex_hex.fullmatch(hex_str):
        return False, "Ce n'est pas du hexadecimal valide."
    return True, "OK"

def chiffrer(message, password):
    sel = secrets.token_bytes(16)
    iv = secrets.token_bytes(TAILLE_BLOC)

    cle_master = deriver_cle(password, sel)
    cle_enc, cle_mac = separer_cles(cle_master)

    cle_bytes = preparer_cle(list(cle_enc))
    ctx = creer_contexte(cle_bytes)

    msg_bytes = bytearray(message.encode('utf-8'))
    données_paddées = ajouter_padding(list(msg_bytes))
    texte_chiffre = []
    bloc_precedent = list(iv)
    for i in range(0, len(données_paddées), TAILLE_BLOC):
        bloc = données_paddées[i:i + TAILLE_BLOC]
        bloc_xore = xor_blocs(bloc, bloc_precedent)
        bloc_chiffre = chiffrer_bloc(bloc_xore, ctx)
        texte_chiffre += bloc_chiffre
        bloc_precedent = bloc_chiffre

    entete = MAGIC + bytes([VERSION]) + sel + iv + bytes(texte_chiffre)

    tag = hmac.new(cle_mac, entete, hashlib.sha256).digest()[:16]

    effacer_buffer(msg_bytes)

    return (entete + tag).hex()

def dechiffrer(hex_str, password):
    ok, raison = verifier_format_hex(hex_str)
    if not ok:
        raise ValueError(raison)

    data = bytes.fromhex(hex_str)

    taille_min = 4 + 1 + 16 + 16 + 16 + 16
    if len(data) < taille_min:
        raise ValueError("Le message est trop court pour etre valide.")

    if data[:4] != MAGIC:
        raise ValueError("Ce message n'a pas ete chiffre par CODEX.")
    if data[4] != VERSION:
        raise ValueError("Version du format non supportee.")

    sel = data[5:21]
    iv = data[21:37]
    tag_recu = data[-16:]
    texte_chiffre = data[37:-16]

    if len(texte_chiffre) == 0 or len(texte_chiffre) % TAILLE_BLOC != 0:
        raise ValueError("Taille dutext invalide.")

    cle_master = deriver_cle(password, sel)
    cle_enc, cle_mac = separer_cles(cle_master)

    tag_attendu = hmac.new(cle_mac, data[:-16], hashlib.sha256).digest()[:16]
    if not comparer_hmac(tag_recu, tag_attendu):
        raise ValueError("Erreur : cle incorrecte ou message modifie.")

    cle_bytes = preparer_cle(list(cle_enc))
    ctx = creer_contexte(cle_bytes)

    texte_clair = []
    bloc_precedent = list(iv)
    for i in range(0, len(texte_chiffre), TAILLE_BLOC):
        bloc = list(texte_chiffre[i:i + TAILLE_BLOC])
        bloc_dechiffre = dechiffrer_bloc(bloc, ctx)
        texte_clair += xor_blocs(bloc_dechiffre, bloc_precedent)
        bloc_precedent = bloc

    resultat = bytes(enlever_padding(texte_clair))
    return resultat.decode('utf-8')

COULEUR_FOND = "#1a1a2e"
COULEUR_CARTE = "#16213e"
COULEUR_VERT = "#00d4aa"
COULEUR_OR = "#ffd166"
COULEUR_ROUGE = "#e94560"
COULEUR_GRIS = "#888888"
COULEUR_TEXTE = "#e0e0e0"
COULEUR_HINT = "#445566"
POLICE = ("Consolas", 11)
POLICE_GRAS = ("Consolas", 11, "bold")

fenetre = tk.Tk()
fenetre.title("CODEX v2.2")
fenetre.configure(bg=COULEUR_FOND)
fenetre.resizable(False, False)

tk.Label(fenetre, text="CODEX",
         font=("Consolas", 17, "bold"),
         bg=COULEUR_FOND, fg=COULEUR_VERT).pack(pady=(18, 2))

frame_etapes = tk.Frame(fenetre, bg=COULEUR_FOND)
frame_etapes.pack(pady=(0, 12))
for i, texte in enumerate(["1. Tape la cle", "2. Tape le message", "3. Clique Chiffrer"]):
    tk.Label(frame_etapes, text=texte,
             font=("Consolas", 10, "bold"),
             bg="#0f3460", fg=COULEUR_VERT,
             padx=10, pady=4).grid(row=0, column=i, padx=4)

tk.Frame(fenetre, bg="#333344", height=1).pack(fill="x", padx=20, pady=(0, 12))

tk.Label(fenetre, text="① Cle secrete :",
         font=POLICE_GRAS, bg=COULEUR_FOND, fg=COULEUR_VERT,
         anchor="w").pack(fill="x", padx=20)

frame_cle = tk.Frame(fenetre, bg=COULEUR_VERT, padx=2, pady=2)
frame_cle.pack(fill="x", padx=20, pady=(2, 2))
champ_cle = tk.Entry(frame_cle,
                     font=POLICE, bg=COULEUR_CARTE, fg=COULEUR_TEXTE,
                     insertbackground=COULEUR_VERT,
                     relief="flat", bd=6, show="*")
champ_cle.pack(fill="x", ipady=6)

tk.Label(fenetre, text="② Message :",
         font=POLICE_GRAS, bg=COULEUR_FOND, fg=COULEUR_VERT,
         anchor="w").pack(fill="x", padx=20)

frame_msg = tk.Frame(fenetre, bg=COULEUR_VERT, padx=2, pady=2)
frame_msg.pack(fill="x", padx=20, pady=(2, 4))
champ_msg = tk.Entry(frame_msg,
                     font=POLICE, bg=COULEUR_CARTE, fg=COULEUR_TEXTE,
                     insertbackground=COULEUR_VERT,
                     relief="flat", bd=6)
champ_msg.pack(fill="x", ipady=6)

TEXTE_PLACEHOLDER = "Tape ton message ici..."
champ_msg.insert(0, TEXTE_PLACEHOLDER)
champ_msg.config(fg=COULEUR_HINT)

def au_focus(_e):
    if champ_msg.get() == TEXTE_PLACEHOLDER:
        champ_msg.delete(0, "end")
        champ_msg.config(fg=COULEUR_TEXTE)
    frame_msg.config(bg=COULEUR_VERT)

def perdu_focus(_e):
    if not champ_msg.get():
        champ_msg.insert(0, TEXTE_PLACEHOLDER)
        champ_msg.config(fg=COULEUR_HINT)
    frame_msg.config(bg="#334455")

champ_msg.bind("<FocusIn>", au_focus)
champ_msg.bind("<FocusOut>", perdu_focus)

frame_boutons = tk.Frame(fenetre, bg=COULEUR_FOND)
frame_boutons.pack(pady=(0, 14))

def lire_message():
    v = champ_msg.get()
    if v == TEXTE_PLACEHOLDER:
        return ""
    return v

def afficher_resultat(texte, couleur=None):
    if couleur is None:
        couleur = COULEUR_VERT
    champ_resultat.config(state="normal", fg=couleur)
    champ_resultat.delete(0, "end")
    champ_resultat.insert(0, texte)
    champ_resultat.config(state="readonly")

def ajouter_historique(ligne):
    historique.config(state="normal")
    historique.insert("end", ligne + "\n")
    historique.see("end")
    historique.config(state="disabled")

def faire_clignoter_rouge(frame):
    frame.config(bg=COULEUR_ROUGE)
    fenetre.after(700, lambda: frame.config(bg=COULEUR_VERT))

def action_chiffrer(*_):
    mdp = champ_cle.get()
    msg = lire_message()

    if not mdp:
        faire_clignoter_rouge(frame_cle)
        barre_statut.config(text="⚠ Entre une cle secrete !", fg=COULEUR_ROUGE)
        return

    if not msg:
        faire_clignoter_rouge(frame_msg)
        barre_statut.config(
            text="⚠ Clique dans le champ message et tape quelque chose !",
            fg=COULEUR_ROUGE)
        champ_msg.focus_force()
        return

    if len(msg) > MAX_MSG:
        faire_clignoter_rouge(frame_msg)
        barre_statut.config(text=f"⚠ Message trop long (max {MAX_MSG} car.)", fg=COULEUR_ROUGE)
        return

    try:
        barre_statut.config(text="Chiffrement en cours... (PBKDF2 peut prendre 1-2 sec)", fg=COULEUR_GRIS)
        fenetre.update()
        resultat = chiffrer(msg, mdp)
        afficher_resultat(resultat, COULEUR_VERT)
        ajouter_historique(f"[CHIFFRE]  {msg[:40]}{'...' if len(msg) > 40 else ''}")
        ajouter_historique(f"           {resultat[:56]}...")
        barre_statut.config(text=f"✓ Chiffre ! ({len(msg)} car. -> {len(resultat)//2} octets)", fg=COULEUR_VERT)
    except Exception as e:
        afficher_resultat("Erreur pendant le chiffrement.", COULEUR_ROUGE)
        barre_statut.config(text=f"⚠ Erreur : {e}", fg=COULEUR_ROUGE)

def action_dechiffrer(*_):
    mdp = champ_cle.get()
    hex_brut = lire_message().strip()

    if not mdp:
        faire_clignoter_rouge(frame_cle)
        barre_statut.config(text="⚠ Entre la cle secrete !", fg=COULEUR_ROUGE)
        return

    if not hex_brut:
        faire_clignoter_rouge(frame_msg)
        barre_statut.config(text="⚠ Colle le texte chiffre (hex) dans le champ message !", fg=COULEUR_ROUGE)
        return

    ok, raison = verifier_format_hex(hex_brut)
    if not ok:
        faire_clignoter_rouge(frame_msg)
        barre_statut.config(text=f"⚠ {raison}", fg=COULEUR_ROUGE)
        return

    try:
        barre_statut.config(text="Dechiffrement en cours...", fg=COULEUR_GRIS)
        fenetre.update()
        resultat = dechiffrer(hex_brut, mdp)
        afficher_resultat(resultat, COULEUR_OR)
        ajouter_historique(f"[DECHIFFRE] {hex_brut[:32]}...")
        ajouter_historique(f"            -> {resultat[:60]}{'...' if len(resultat) > 60 else ''}")
        barre_statut.config(text="✓ Dechiffrement ok et integrite verifiee !", fg=COULEUR_OR)
    except Exception as e:
        afficher_resultat("Echec. Cle incorrecte ou message modifie.", COULEUR_ROUGE)
        barre_statut.config(text=f"⚠ {str(e)}", fg=COULEUR_ROUGE)

def action_effacer():
    champ_msg.delete(0, "end")
    champ_msg.insert(0, TEXTE_PLACEHOLDER)
    champ_msg.config(fg=COULEUR_HINT)
    champ_cle.delete(0, "end")
    afficher_resultat("")
    barre_statut.config(text="Tout efface.", fg=COULEUR_GRIS)
    champ_msg.focus_force()

def action_copier():
    res = champ_resultat.get().strip()
    if res:
        fenetre.clipboard_clear()
        fenetre.clipboard_append(res)
        barre_statut.config(text="✓ Copie dans le presse-papiers !", fg=COULEUR_VERT)
    else:
        barre_statut.config(text="Rien a copier.", fg=COULEUR_GRIS)

def fermer_fenetre():
    champ_cle.delete(0, 'end')
    champ_msg.delete(0, 'end')
    fenetre.destroy()

fenetre.protocol("WM_DELETE_WINDOW", fermer_fenetre)

for texte_btn, couleur_btn, commande in [
    ("③ Chiffrer", "#0f3460", action_chiffrer),
    ("   Dechiffrer", "#2d6a4f", action_dechiffrer),
    ("   Effacer", "#444444", action_effacer),
]:
    tk.Button(frame_boutons,
              text=texte_btn,
              font=POLICE_GRAS,
              bg=couleur_btn, fg="#ffffff",
              activebackground=couleur_btn,
              relief="flat", padx=16, pady=9,
              cursor="hand2",
              command=commande).pack(side="left", padx=5)

champ_msg.bind("<Return>", action_chiffrer)
fenetre.bind("<Control-d>", action_dechiffrer)

tk.Frame(fenetre, bg="#333344", height=1).pack(fill="x", padx=20, pady=(0, 10))
tk.Label(fenetre, text="Resultat :",
         font=POLICE_GRAS, bg=COULEUR_FOND, fg=COULEUR_TEXTE,
         anchor="w").pack(fill="x", padx=20)

frame_resultat = tk.Frame(fenetre, bg="#334455", padx=2, pady=2)
frame_resultat.pack(fill="x", padx=20, pady=(2, 6))
champ_resultat = tk.Entry(frame_resultat,
                          font=("Consolas", 10),
                          bg=COULEUR_CARTE, fg=COULEUR_VERT,
                          insertbackground=COULEUR_VERT,
                          relief="flat", bd=6,
                          state="readonly",
                          readonlybackground=COULEUR_CARTE)
champ_resultat.pack(fill="x", ipady=6)

tk.Button(fenetre, text="Copier le resultat",
          font=POLICE_GRAS,
          bg="#555555", fg="#ffffff",
          activebackground="#555555",
          relief="flat", padx=14, pady=6,
          cursor="hand2",
          command=action_copier).pack(pady=(0, 10))

tk.Label(fenetre, text="Historique :",
         font=POLICE_GRAS, bg=COULEUR_FOND, fg=COULEUR_TEXTE,
         anchor="w").pack(fill="x", padx=20)

frame_histo = tk.Frame(fenetre, bg=COULEUR_CARTE)
frame_histo.pack(fill="x", padx=20, pady=(2, 12))

historique = tk.Text(frame_histo,
                     width=60, height=5,
                     font=("Consolas", 9),
                     bg=COULEUR_CARTE, fg=COULEUR_GRIS,
                     relief="flat", bd=4,
                     wrap="word", state="disabled")
scrollbar = tk.Scrollbar(frame_histo, command=historique.yview, bg=COULEUR_CARTE)
historique.configure(yscrollcommand=scrollbar.set)
historique.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

barre_statut = tk.Label(fenetre,
                        text="Pret.  |  Entree = Chiffrer  |  Ctrl+D = Dechiffrer",
                        font=("Consolas", 9),
                        bg=COULEUR_FOND, fg=COULEUR_GRIS)
barre_statut.pack(pady=(0, 12))

fenetre.after(200, champ_msg.focus_force)

fenetre.mainloop()