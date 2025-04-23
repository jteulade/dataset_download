Le premier problème rencontré a été l'installation des packages requis pour faire fonctionner le projet. J'ai d'abord essayé la commande suivante :  
```
pip install -r requirements.txt
```
Cependant, j'ai rencontré des erreurs indiquant que je n'avais pas les bonnes versions des packages disponibles. Dans un premier temps, j'ai essayé d'installer un environnement Python avec `venv`, mais après discussion avec mon tuteur, j'ai remarqué qu'il serait plus intéressant d'utiliser `conda`, car il offre plus de fonctionnalités, notamment pour gérer les différents systèmes d'exploitation. J'ai donc installé `conda` et pu installer les packages requis assez facilement. J'ai également ajouté cette méthode dans le fichier `README.md` pour expliquer comment installer les packages nécessaires.

Ensuite, j'ai entrepris d'utiliser `logging` au lieu des `print` afin de rendre les messages plus explicites pour l'utilisateur. Cela permet d'indiquer si un message est une information, un avertissement ou une erreur, et ainsi de détecter les problèmes plus facilement. J'ai donc ajouté des logs dans tous les fichiers qui en avaient besoin.

Pour la gestion des exceptions, j'ai ajouté des exceptions spécifiques pour chaque cas afin de pouvoir capturer les erreurs dès qu'elles apparaissent.

Enfin, concernant la gestion des paramètres, j'ai corrigé un problème dans le script `sentinel_city_explorer.py`. Si l'utilisateur choisissait une date comme filtre durant laquelle Sentinel-2 n'avait pas de données, le code affichait une erreur mais continuait à télécharger, alors que la suite du code nécessitait 4 mosaïques pour chaque tuile. Désormais, en cas d'erreur, le programme s'arrête immédiatement pour éviter de télécharger davantage et informe l'utilisateur de la situation.

J'ai aussi rajoute de la documentation avec `docstring`.

Je vais maintenant mettre des exemples d'utilisations de chaques scripts.

Quand on applique des filtres et qu'on tombe sur une tuile d'une île, pour obtenir sa tuile voisine, si celle-ci est uniquement composée d'eau, on conserve tout de même la tuile. Cela entraîne une situation où l'on dispose de seulement 4 mosaïques au lieu des 8 nécessaires pour une ville. 
Il serait peut-etre ne pas selectionne la tuile si on ne trouve pas de tuile voisine.

J'ai eu un probleme car le script bash que j'avais fais ne nous permettait pas de rester sur conda car toute modification de l'environnement (comme l'activation de Conda) est limitée à la session du script et ne persiste pas dans le terminal parent. On doit donc utiliser le . avant d'executer le script.res et qu'on tombe sur une tuile d'une île, pour obtenir sa tuile voisine, si celle-ci est uniquement composée d'eau, on conserve tout de même la tuile. Cela entraîne une situation où l'on dispose de seulement 4 mosaïques au lieu des 8 nécessaires pour une ville. 
Il serait peut-etre ne pas selectionne la tuile si on ne trouve pas de tuile voisine.

J'ai eu un probleme car le script bash que j'avais fais ne nous permettait pas de rester sur conda car toute modification de l'environnement (comme l'activation de Conda) est limitée à la session du script et ne persiste pas dans le terminal parent. On doit donc utiliser le . avant de d'executer le script.