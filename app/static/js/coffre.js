// Coffre-fort : bouton "Copier le lien". Sans ce script, le lien reste lisible et copiable à la main.
document.addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("[data-copier]");
  if (!bouton) {
    return;
  }
  const champ = document.getElementById(bouton.dataset.copier);
  const statut = document.querySelector("[data-statut-copie]");
  const afficher = (texte) => {
    if (statut) {
      statut.textContent = texte;
    }
  };
  champ.select();
  if (navigator.clipboard) {
    navigator.clipboard.writeText(champ.value).then(
      () => afficher("Lien copié."),
      () => afficher("Copie impossible : sélectionne le lien et copie-le à la main."),
    );
  } else {
    afficher("Copie impossible : sélectionne le lien et copie-le à la main.");
  }
});
