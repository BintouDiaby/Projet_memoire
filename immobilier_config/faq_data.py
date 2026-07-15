"""FAQ du centre d'aide (/aide/) — réutilisée aussi par l'assistant IA
(voir assistant/tools.py::chercher_aide) pour répondre aux questions
fréquentes sans appeler l'API."""

FAQ_CATEGORIES = [
    {
        'id': 'location', 'label': 'Location',
        'questions': [
            ("Comment demander une visite d'un bien ?", "Ouvrez la fiche du bien qui vous intéresse et cliquez sur « Demander une visite ». Choisissez une date et un message facultatif ; le propriétaire reçoit votre demande et peut la confirmer ou la refuser depuis son tableau de bord."),
            ("Comment réserver un bien ?", "Si vous avez une visite confirmée pour ce bien, un bouton « Réserver ce bien » apparaît sur sa fiche. La réservation bloque le bien pendant 72h le temps que le contrat soit préparé."),
            ("Que se passe-t-il après ma réservation ?", "Le propriétaire prépare un contrat en brouillon puis vous l'envoie pour signature électronique. Vous devez cocher « j'ai lu et j'accepte » et signer avant que le contrat ne devienne actif."),
        ],
    },
    {
        'id': 'construction', 'label': 'Construction',
        'questions': [
            ("Comment demander un devis pour construire ?", "Depuis « Construction », parcourez les entreprises, ouvrez leur profil et cliquez sur « Demander un devis ». Décrivez votre projet ; l'entreprise vous répondra avec un montant chiffré."),
            ("Comment accepter ou refuser un devis reçu ?", "Sur la page de suivi de votre projet, le devis s'affiche avec son montant et son détail. Vous pouvez l'accepter directement, ou le refuser en indiquant un motif — l'entreprise pourra alors vous envoyer un devis révisé."),
            ("Comment suivre l'avancement de mon chantier ?", "La page de votre projet affiche la progression en %, les étapes du chantier (fondations, élévation, toiture...) et les photos ajoutées par l'entreprise au fil des travaux."),
        ],
    },
    {
        'id': 'paiements', 'label': 'Paiements',
        'questions': [
            ("Comment payer mon loyer ?", "Chaque mois, une facture est générée automatiquement. Depuis sa page, vous pouvez payer en ligne ou demander un rendez-vous pour un paiement en espèces auprès de votre propriétaire."),
            ("Que se passe-t-il si je suis en retard ?", "Selon les clauses de votre contrat, vous recevez d'abord un rappel, puis d'éventuels frais de retard peuvent s'appliquer si le retard se prolonge. En cas de retard important, le propriétaire peut vous envoyer une mise en demeure formelle avec un délai de régularisation."),
            ("Où voir l'historique de mes paiements ?", "Votre espace locataire liste tous vos paiements passés, avec leur statut (reçu, en retard...). Chaque facture est aussi téléchargeable individuellement."),
        ],
    },
    {
        'id': 'contrats', 'label': 'Contrats',
        'questions': [
            ("Comment signer mon contrat ?", "Une fois le contrat envoyé par le propriétaire, ouvrez-le depuis « Mes contrats », relisez les articles, cochez la case de confirmation puis cliquez sur « Je signe »."),
            ("Puis-je télécharger mon contrat signé ?", "Oui, un PDF récapitulatif est disponible à tout moment depuis la page du contrat."),
        ],
    },
    {
        'id': 'compte', 'label': 'Mon compte',
        'questions': [
            ("Comment modifier mes informations personnelles ?", "Rendez-vous sur « Mon profil » puis « Modifier » pour changer votre nom, téléphone, photo ou préférences de confidentialité."),
            ("Comment confirmer mon adresse email ?", "Un code à 6 chiffres vous est envoyé à l'inscription. Vous pouvez le ressaisir ou en redemander un depuis votre espace si besoin."),
        ],
    },
    {
        'id': 'messagerie', 'label': 'Messagerie',
        'questions': [
            ("Comment contacter un propriétaire ou une entreprise ?", "Depuis la fiche d'un bien, d'une entreprise ou d'un projet, une conversation démarre automatiquement dès votre première demande (visite, devis...)."),
            ("Puis-je modifier ou supprimer un message envoyé ?", "Oui, survolez votre message dans la conversation pour faire apparaître les options modifier / supprimer."),
        ],
    },
    {
        'id': 'parametres', 'label': 'Paramètres',
        'questions': [
            ("Comment gérer mes notifications ?", "Votre centre de notifications liste tout ce qui vous concerne ; vous pouvez marquer comme lu ou supprimer chaque notification individuellement."),
            ("Comment changer mon mot de passe ?", "Depuis « Paramètres », utilisez le formulaire de changement de mot de passe dédié."),
        ],
    },
]
