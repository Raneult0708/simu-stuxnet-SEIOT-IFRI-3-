Windows — com0com

Installation :

Télécharge le driver signé (important, sinon problèmes avec Windows 10/11) : https://sourceforge.net/projects/com0com/ — prends la version depuis le lien "com0com-3.0.0.0-x64-fre-signed.zip" ou équivalent signé.
Installe en tant qu'administrateur. Pendant l'installation, il peut y avoir un avertissement "pilote non certifié" selon ta version de Windows — accepte (c'est un driver légitime, juste pas signé par Microsoft directement).

Créer la paire de ports :
3. Lance "Setup Command Prompt" (installé avec com0com, cherche-le dans le menu Démarrer).
4. Dans cette invite de commande spéciale :

list

pour voir les paires existantes, puis crée la tienne :

install PortName=COM10 PortName=COM11
Vérifie dans le Gestionnaire de périphériques (devmgmt.msc) → "Ports (COM & LPT)" que COM10 et COM11 apparaissent bien.

Utilisation :

LabVIEW se connecte sur COM10 (VISA Resource Name = COM10)
Ton script Python utilise COM11 comme PORT_LABVIEW
L'Arduino reste sur son port physique réel (ex: COM3, COM4 — vérifie dans le Gestionnaire de périphériques après branchement USB)
macOS — socat

Installation (via Homebrew) :

bash
brew install socat

Créer la paire de ports virtuels :

bash
socat -d -d pty,raw,echo=0,link=/tmp/ttyLabVIEW pty,raw,echo=0,link=/tmp/ttyScript

Cette commande doit rester lancée dans un terminal dédié tant que tu travailles (elle maintient le pont actif). Elle va créer deux liens symboliques lisibles :

/tmp/ttyLabVIEW (côté LabVIEW)
/tmp/ttyScript (côté ton script Python)

Utilisation :

LabVIEW VISA Resource Name → /tmp/ttyLabVIEW
Ton script Python : PORT_LABVIEW = "/tmp/ttyScript"
Arduino : cherche son port avec ls /dev/tty.usb* ou ls /dev/cu.usb* après branchement.

⚠️ Attention macOS + LabVIEW : NI LabVIEW sur Mac peut avoir des soucis de compatibilité VISA avec des ports pty non standards. Si ça pose problème pendant les tests, il faudra basculer cette machine en Linux/Windows pour la partie LabVIEW, et garder macOS uniquement pour le script Python si besoin.

Linux — socat

Installation :

bash
sudo apt install socat        # Debian/Ubuntu
sudo dnf install socat         # Fedora

Créer la paire :

bash
socat -d -d pty,raw,echo=0,link=/tmp/ttyLabVIEW pty,raw,echo=0,link=/tmp/ttyScript

Même logique qu'macOS — laisse ce terminal ouvert, c'est le pont actif.

Utilisation :

LabVIEW → /tmp/ttyLabVIEW
Script Python → /tmp/ttyScript
Arduino → cherche avec ls /dev/ttyUSB* ou ls /dev/ttyACM*, et donne les droits si besoin : sudo usermod -aG dialout $USER (puis redémarre la session).

Rappel pour la bibliothèque keyboard sur Linux : il faudra lancer le script Python avec sudo, sinon la détection de la touche 'b' ne fonctionnera pas (accès bas niveau au clavier). Ça veut dire que ton pip install des dépendances doit être accessible aussi en mode sudo, ou utiliser un environnement virtuel accessible avec les bons droits — pense à tester ça avant la démo pour éviter une surprise de dernière minute.