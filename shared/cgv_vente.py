"""Conditions Générales de Vente EMS — texte de référence unique.

Source : CGV_EMERAUDE_MOTEURS_SYSTEMES_2026_08_2pages.pdf (Version 2026.01,
applicable à compter du 10/08/2026), transcrit à l'identique.
Jointes aux accusés de réception de commande générés depuis une affaire
(shared/affaire_pdf.py, pdf_type="accuse_reception").

Pour une nouvelle version : modifier CGV_VENTE_VERSION et CGV_VENTE_ARTICLES.
Structure : liste d'articles (titre, blocs) ; un bloc est soit un paragraphe
(str), soit un sous-titre ("sub", "2.1 Matériels"), soit un paragraphe en
gras ("strong", "...").
"""

CGV_VENTE_TITRE = "Conditions générales de vente"
CGV_VENTE_VERSION = "Version 2026.01 – Applicable à compter du 10/08/2026"

CGV_VENTE_ARTICLES = [
    ("Article 1 – Champ d'application et opposabilité", [
        "Les présentes conditions générales de vente (les « CGV ») s'appliquent à l'ensemble des offres, devis, accusés de réception de commande et ventes de matériels, moteurs, systèmes et pièces détachées réalisés par EMERAUDE MOTEURS SYSTEMES (« EMS ») au profit de ses clients professionnels (le « Client »). Les prestations de services (diagnostic, dépannage, réparation, entretien, maintenance, installation, mise en service et essais), en atelier ou sur site, sont régies par les Conditions Générales de Prestations de Services et d'Interventions d'EMS, qui complètent les présentes ; en cas de contradiction, les Conditions Services prévalent pour ce qui concerne les prestations.",
        "Toute commande adressée à EMS, de même que l'acceptation d'un devis ou d'un accusé de réception de commande, emporte, en l'absence de contrat particulier ou d'accord écrit valant contrat, adhésion pleine et entière aux présentes CGV, lesquelles prévalent sur toutes conditions générales d'achat ou tout autre document du Client, conformément à l'article L.441-1 du Code de commerce.",
        "Le fait pour EMS de ne pas se prévaloir à un moment donné de l'une quelconque des clauses des présentes ne vaut pas renonciation à s'en prévaloir ultérieurement.",
    ]),
    ("Article 2 – Offres et devis", [
        ("sub", "2.1 Matériels"),
        "Les caractéristiques des produits proposés à la vente par EMS lui sont communiquées par ses fournisseurs au moyen de documents mis à disposition. EMS, n'ayant pas compétence de contrôle de ceux-ci, ne peut être tenue pour responsable en cas d'erreur ou d'information erronée qui serait introduite dans les documents techniques ou commerciaux des fabricants ou dans ses propres documents.",
        ("sub", "2.2 Spécifications"),
        "EMS ne peut être tenue pour responsable des conséquences qui pourraient survenir dans le cas de changements dans les spécifications des produits ou matériels qu'elle commercialise, dès lors que ces changements sont le fait des fabricants.",
        ("sub", "2.3 Prix"),
        "Les prix figurant dans les offres et tarifs d'EMS sont établis hors taxes sur la base des conditions économiques en vigueur à la date de l'offre. Ils peuvent être révisés lorsque les éléments de calcul dont les valeurs sont du ressort des autorités politiques, administratives ou monétaires évoluent, ces circonstances constituants par ailleurs, le cas échéant, un cas de force majeure autorisant EMS à réajuster éventuellement ses offres et ses tarifs.",
        ("sub", "2.4 Validité et délais"),
        "Sauf stipulation contraire, les offres et devis d'EMS sont valables trente (30) jours calendaires à compter de leur émission. Sauf pour les marchandises disponibles sur stock et dans la limite de validité spécifiée dans les offres, les délais indiqués ne valent que pour information, les délais réels étant ceux confirmés par les fournisseurs d'EMS le jour de la réception des commandes, auxquels s'ajoutent les délais des transporteurs et affréteurs.",
    ]),
    ("Article 3 – Commandes", [
        "Pour des raisons d'efficacité et de rapidité dans l'exécution des commandes, seules les commandes dont les délais atteignent ou dépassent huit (8) jours ouvrables feront l'objet d'un accusé de réception de commande écrit par EMS. Toute modification ou annulation de commande par le Client est subordonnée à l'accord écrit et préalable d'EMS ; les coûts déjà engagés restent en tout état de cause à la charge du Client.",
        "Certains matériels devant faire l'objet d'une homologation technique après installation, EMS se réserve le droit de ne pas accepter de commande de ces matériels sans garantie satisfaisante d'obtention de cette homologation. Pour toutes opérations commerciales, EMS se réserve le droit de refuser de livrer, sauf contre paiement avant expédition ou garantie satisfaisante.",
    ]),
    ("Article 4 – Livraisons", [
        ("sub", "4.1 Délais"),
        "Sauf stipulation contraire du Client clairement exprimée au moment de la commande et acceptée par EMS, les livraisons sont faites au fur et à mesure des disponibilités des matériels. EMS ne peut être tenue pour responsable des retards ou de la non-exécution des livraisons du fait du mauvais temps, de grèves ou autres conflits du travail, du fait du prince, ou de tout autre cas de force majeure au sens de l'article 10 des présentes. Le retard de livraison ne peut donner lieu ni à pénalité ni à annulation de la commande, sauf accord écrit contraire.",
        ("sub", "4.2 Risques et transport"),
        "Sauf stipulation contraire ou Incoterm expressément convenu, la livraison est réputée effectuée et les risques transférés au Client lors de la remise des marchandises au premier transporteur, qui devra faire toute réserves à la livraison puis protestation motivée adressée au transporteur dans les trois jours, hors fériés, par lettre recommandée ou acte extrajudiciaire auprès du transporteur, seul responsable en cas de retard, vol, perte ou avarie, conformément aux articles L.133-3 et suivants du Code de commerce.",
        ("sub", "4.3 Emballages"),
        "Sauf stipulation contraire, les emballages ne sont pas consignés et ne doivent pas être retournés ; ils ne peuvent faire l'objet d'avoir ou de remise. Dans le cas d'un emballage consigné, celui-ci doit être retourné franco de port dans les quinze (15) jours qui suivent la livraison. Passé ce délai, il sera facturé au prix indiqué sur le bordereau de consignation accompagnant la facture du matériel.",
        ("sub", "4.4 Réclamations"),
        "Pour être recevable, toute réclamation relative à l'état apparent ou à la conformité des marchandises devra nous être adressée par écrit dans les quarante-huit (48) heures de leur réception. La transformation, la modification ou la revente des marchandises vaut renonciation à toute réclamation fondée sur un défaut apparent ou une non-conformité qui pouvait raisonnablement être constatée avant cette opération, sans préjudice des garanties légales applicables et des défauts non apparents.",
        ("sub", "4.5 Livraisons et installations à bord de navires"),
        "Lorsque la livraison ou l'installation du matériel vendu intervient à bord d'un navire, celui-ci, ses apparaux, ses équipements et sa cargaison demeurent la propriété exclusive du Client et restent placés sous sa garde juridique, sa direction et sa responsabilité, ainsi que, le cas échéant, sous l'autorité de son capitaine, quel que soit le lieu où le navire se trouve (à quai, au mouillage, en cale sèche, sur terre-plein ou en cours d'essais). L'intervention d'EMS, limitée au matériel objet de la vente, n'emporte aucun transfert de la garde du navire au sens de l'article 1242 du Code civil, ni constitution d'un dépôt, y compris en l'absence du Client, de son équipage ou de tout représentant à bord. Le Client conserve à sa charge la sécurité du navire, les autorisations portuaires ou maritimes et l'assurance du navire (corps et machines) et de sa responsabilité civile pendant toute la durée des opérations. Les modalités détaillées des interventions à bord sont précisées aux Conditions Générales de Prestations de Services et d'Interventions d'EMS.",
    ]),
    ("Article 5 – Facturation", [
        "La livraison des marchandises ou l'exécution des prestations, objet des commandes des Clients, déclenche l'édition des factures d'EMS, établies suivant les présentes CGV et les accords conclus avec les Clients préalablement à la commande. Les conditions de règlement figurant sur les factures sont réputées non négociables.",
    ]),
    ("Article 6 – Paiement", [
        ("sub", "6.1 Modalités et délais de paiement"),
        "Sauf convention contraire, les factures sont payables à trente (30) jours à compter de leur date d'émission. En tout état de cause, le délai de paiement convenu ne peut dépasser soixante (60) jours à compter de la date d'émission de la facture, ou quarante-cinq (45) jour fin de mois, conformément à l'article L.441-10 du Code de commerce. Le paiement s'entend de l'encaissement effectif à l'échéance ; il appartient au Client de prendre ses dispositions pour faire parvenir son règlement en temps utile.",
        ("sub", "6.2 Paiement entre les mains du factor – subrogation"),
        "EMS a conclu un contrat d'affacturage. Le Client est informé que les créances d'EMS peuvent être transférées par subrogation à un établissement de crédit spécialisé dont l'identité et les coordonnées figurent sur les factures. Lorsque la facture porte la mention de subrogation, seul le paiement effectué directement entre les mains du factor est libératoire ; tout paiement effectué entre les mains d'EMS en violation de cette mention n'aura pas d'effet libératoire à l'égard du factor.",
        ("sub", "6.3 Paiement anticipé – escompte"),
        "Le paiement anticipé de nos factures, dès accord de notre part, donnera lieu à un escompte au taux de 0,5 % par période entière d'un mois. L'obtention et le montant de cet escompte ne seront effectifs qu'après constat de la date réelle de règlement. En cas d'escompte pour paiement comptant ou anticipé, celui-ci fera l'objet soit d'une note de crédit, soit d'un crédit sur le compte du Client, les deux cas étant assujettis au régime normal de la TVA.",
        ("sub", "6.4 Retard ou défaut de paiement"),
        "Tout retard de paiement entraîne de plein droit, sans qu'une mise en demeure soit nécessaire : (i) l'exigibilité immédiate de toutes les sommes restant dues, quel que soit leur mode de règlement et la date de règlement prévue (déchéance du terme) ; (ii) l'application de pénalités de retard calculées au taux d'intérêt appliqué par la Banque centrale européenne à son opération de refinancement la plus récente majoré de dix (10) points de pourcentage, conformément à l'article L.441-10 du Code de commerce, courant à compter du jour suivant la date d'échéance jusqu'au complet paiement ; (iii) le versement d'une indemnité forfaitaire pour frais de recouvrement de quarante (40) euros par facture impayée, conformément aux articles L.441-10 et D.441-5 du Code de commerce, sans préjudice d'une indemnisation complémentaire, sur justification, lorsque les frais de recouvrement exposés sont supérieurs à ce montant ; (iv) la faculté pour EMS de suspendre les livraisons et prestations en cours et de subordonner toute nouvelle commande à un paiement comptant ou à la fourniture de garanties.",
        ("sub", "6.5 Compensation"),
        "Le Client s'interdit expressément de procéder à toute compensation, retenue ou déduction unilatérale sur les sommes dues à EMS, sans l'accord écrit et préalable de celle-ci. EMS pourra en revanche compenser toute somme qu'elle devrait au Client avec toutes créances et dettes réciproques échues et exigibles, après en avoir notifié le Client.",
        ("sub", "6.6 Acomptes et trop-perçus"),
        "EMS se réserve le droit de conserver tout acompte, avoir, trop-perçu ou autre somme qui viendrait à se trouver dans sa comptabilité au crédit du compte d'un Client se trouvant en défaut de paiement ; ces sommes seront alors déduites du règlement final, à l'exception des éventuels intérêts et pénalités de retard.",
    ]),
    ("Article 7 – Réserve de propriété", [
        "Conformément aux articles 2367 et suivants du Code civil, les marchandises livrées restent la propriété d'EMS jusqu'au complet paiement de leur prix en principal et accessoires. Le paiement, qui fera foi du transfert de propriété, s'entend de l'encaissement effectif. Ne constitue pas un paiement au sens de la présente clause la remise d'un effet de commerce ou de tout titre créant une obligation de payer.",
        "Nonobstant la présente clause de réserve de propriété, les risques afférents aux marchandises, notamment les risques de perte, de vol, de destruction ainsi que les dommages causés ou subis par celles-ci, sont transférés au Client dès leur remise au premier transporteur, conformément à l'article 4.2 des présentes, à charge pour le Client de les assurer. La perte ou la détérioration des marchandises postérieurement au transfert des risques ne libère pas le Client de son obligation de paiement.",
        "Le Client peut revendre ou transformer les marchandises dans le cadre de l'exploitation normale de son activité ; cette autorisation de revente est retirée automatiquement en cas de cessation des paiements du Client. En cas de revente, le Client cède à EMS, à due concurrence des sommes restant dues, la créance de prix de revente.",
        "En cas de saisie opérée par des tiers sur des marchandises livrées et facturées par EMS mais non encore payées, le Client est tenu d'en informer immédiatement EMS et de faire connaître au tiers saisissant l'existence de la présente clause.",
    ]),
    ("Article 8 – Garanties", [
        ("sub", "8.1 Étendue"),
        "La garantie contractuelle s'applique à tout défaut de matière ou de construction. Elle ne couvre que les pièces et composants d'origine fournis par EMS et uniquement dans la mesure où le matériel a été installé, utilisé et entretenu conformément aux préconisations du constructeur et/ou d'EMS. La durée de la garantie est la suivante : six (6) mois pour les pièces, à compter de leur livraison ; douze (12) mois pour les matériels ou équipements, à compter de leur mise en service, jusqu'à un maximum de dix-huit (18) mois à partir de leur date de livraison.",
        "La réparation ou le remplacement des pièces effectué dans le cadre de la garantie n'a pas pour effet de prolonger le délai de garantie des autres composants du matériel. La garantie couvre uniquement les frais de réparation ou de remplacement. En aucun cas, l'immobilisation du matériel, le délai de réparation ou d'échange, les coûts de transport, les frais de démontage et de remontage, ainsi que les dommages causés aux installations environnantes, ne peuvent donner lieu au versement d'une indemnité quelconque par EMS au profit du Client.",
        ("sub", "8.2 Modalités"),
        "Les prestations résultant de l'application de la garantie sont effectuées en principe dans les ateliers d'EMS, après que le Client ait renvoyé à celle-ci le matériel et sollicité par écrit l'application de la garantie. La garantie n'est accordée qu'après examen des pièces ou composants défectueux retournés à EMS. Toute pièce reconnue défectueuse est remplacée gratuitement par EMS ou réparée dans son atelier. Le choix entre la réparation ou le remplacement au titre de la garantie, ainsi que les modalités d'exécution de ces différentes opérations, relève de la compétence exclusive d'EMS. Tout matériel ou pièce remplacée en application de la garantie devient la propriété d'EMS.",
        ("sub", "8.3 Exclusions"),
        "La garantie ne couvre pas les coûts de transfert du matériel ou des pièces défectueuses, ni celui du retour du matériel ou des pièces réparées ou remplacées, lesquels coûts demeurent toujours à la charge du Client. De même, en cas de réparation sur le site d'installation, les frais de déplacement et de séjour des techniciens d'EMS sont à la charge du Client. La garantie est exclue pour les incidents dus à des cas fortuits ou de force majeure, pour tout remplacement ou réparation résultant d'une usure normale ou provenant de négligences, d'un défaut de surveillance ou d'entretien, ou d'une utilisation dans des conditions non conformes aux préconisations du constructeur et/ou d'EMS. Tout matériel livré ou commandé avant l'acceptation de la mise en œuvre de la présente garantie sera facturé au Client. Sauf accord spécifique préalable et écrit d'EMS, la garantie s'exerce exclusivement sur le territoire français.",
        ("sub", "8.4 Garanties légales"),
        "Les stipulations qui précèdent ne font pas obstacle à l'application de la garantie légale des vices cachés prévue aux articles 1641 et suivants du Code civil, dans les conditions et limites prévues par la loi entre professionnels.",
    ]),
    ("Article 9 – Responsabilité", [
        "La responsabilité d'EMS est strictement limitée aux obligations définies aux présentes. Sauf faute lourde ou dolosive, la responsabilité d'EMS, toutes causes confondues, est plafonnée au montant hors taxes de la commande concernée. EMS ne pourra en aucun cas être tenue à la réparation des dommages indirects ou immatériels subis par le Client, tels que notamment perte de production, perte de profit, perte de chance, perte de données ou préjudice commercial.",
        ("sub", "9.1 Exclusion des pertes d'exploitation"),
        "Il est expressément convenu qu'EMS ne pourra en aucun cas être tenue de réparer les pertes d'exploitation subies par le Client ou par des tiers, quelle qu'en soit la cause ou l'origine, y compris lorsqu'elles résultent d'un défaut, d'une panne ou d'une immobilisation du matériel vendu, réparé ou installé, d'un retard de livraison, d'une intervention au titre de la garantie ou de l'indisponibilité de pièces de rechange. Par pertes d'exploitation, il faut entendre notamment toute perte de chiffre d'affaires, de marge, de production ou de revenus, tout surcoût d'exploitation, ainsi que les frais d'immobilisation, de location de matériel de remplacement ou de personnel. Le Client déclare faire son affaire personnelle de l'assurance de ces risques et renonce, ainsi que ses assureurs, à tout recours contre EMS et ses assureurs à ce titre. La présente exclusion constitue une condition essentielle du consentement d'EMS, dont il a été tenu compte dans la détermination du prix.",
    ]),
    ("Article 10 – Force majeure", [
        "Conformément à l'article 1218 du Code civil, aucune des parties ne pourra être tenue pour responsable de l'inexécution de ses obligations si cette inexécution résulte d'un événement échappant à son contrôle, qui ne pouvait être raisonnablement prévu lors de la conclusion du contrat et dont les effets ne peuvent être évités par des mesures appropriées. Sont notamment considérés comme cas de force majeure, outre les événements habituellement retenus par la jurisprudence : les intempéries exceptionnelles, grèves et conflits du travail (y compris chez les fournisseurs et transporteurs), pénuries de matières premières ou de composants, épidémies, décisions des autorités et fait du prince. Si l'empêchement est temporaire, l'exécution des obligations est suspendue ; s'il est définitif, le contrat est résolu de plein droit et les parties sont libérées de leurs obligations dans les conditions prévues aux articles 1351 et 1351-1 du Code civil.",
    ]),
    ("Article 11 – Données personnelles", [
        "EMS, agissant en qualité de responsable du traitement, collecte et traite les données à caractère personnel relatives au Client, à ses représentants, salariés et interlocuteurs, nécessaires à la gestion de la relation commerciale.",
        "Ces données sont traitées aux fins de gestion des demandes, offres, devis, commandes, livraisons et garanties, de suivi de la relation contractuelle, de facturation, de comptabilité, de financement et de recouvrement des créances, de gestion des réclamations et contentieux, ainsi que de respect des obligations légales et réglementaires auxquelles EMS est soumise.",
        "Les traitements reposent, selon leur finalité, sur l'exécution du contrat ou de mesures précontractuelles, sur le respect des obligations légales d'EMS, ainsi que sur son intérêt légitime à assurer la gestion de sa relation commerciale, le financement et le recouvrement de ses créances et la défense de ses droits.",
        "Les données sont destinées aux membres du personnel d'EMS habilités à les traiter ainsi qu'à ses prestataires, conseils, assureurs, établissements financiers et partenaires chargés du financement ou du recouvrement de ses créances. Elles peuvent notamment être communiquées au factor d'EMS lorsque les créances concernées lui sont transférées. Elles peuvent également être transmises aux autorités administratives ou judiciaires lorsque la loi l'exige.",
        "Les données sont conservées pendant la durée nécessaire à la gestion de la relation contractuelle, puis archivées pendant les durées requises par les obligations légales applicables et pendant les délais nécessaires à la constatation, à l'exercice ou à la défense des droits d'EMS.",
        "Dans les conditions prévues par la réglementation applicable, les personnes concernées disposent d'un droit d'accès, de rectification, d'effacement et de limitation du traitement de leurs données, ainsi que d'un droit d'opposition et, lorsqu'il est applicable, d'un droit à la portabilité de leurs données.",
        "Ces droits peuvent être exercés en écrivant à EMS. Les personnes concernées disposent également du droit d'introduire une réclamation auprès de la Commission nationale de l'informatique et des libertés.",
    ]),
    ("Article 12 – Droit applicable et attribution de compétence", [
        "Les présentes CGV et toutes les ventes et prestations qu'elles régissent sont soumises au droit français, à l'exclusion expresse de la Convention des Nations Unies sur les contrats de vente internationale de marchandises (Convention de Vienne de 1980).",
        ("strong", "IL EST EXPRESSEMENT SPECIFIE QUE TOUT LITIGE POUVANT SE REVELER ENTRE EMS ET L'UN DE SES CLIENTS AU COURS D'UNE OPERATION RELEVANT DES PRESENTES, Y COMPRIS EN CAS DE PLURALITE DE DEFENDEURS OU D'APPEL EN GARANTIE, SERA DU RESSORT DU SEUL TRIBUNAL DE COMMERCE DE SAINT-MALO."),
    ]),
]


def cgv_vente_clauses_html(esc) -> str:
    """HTML des articles (une <div class="clause"> par article, même balisage
    que les conditions générales des devis). `esc` = fonction d'échappement."""
    out = []
    for titre, blocs in CGV_VENTE_ARTICLES:
        parts = [f"<h5>{esc(titre)}</h5>"]
        for b in blocs:
            if isinstance(b, tuple):
                kind, txt = b
                if kind == "sub":
                    parts.append(f'<h6>{esc(txt)}</h6>')
                else:
                    parts.append(f"<p><strong>{esc(txt)}</strong></p>")
            else:
                parts.append(f"<p>{esc(b)}</p>")
        out.append('<div class="clause">' + "".join(parts) + "</div>")
    return "\n".join(out)
