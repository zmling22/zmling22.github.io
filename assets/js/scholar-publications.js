(function () {
  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function validUrl(value) {
    return /^https?:\/\//.test(String(value || ""));
  }

  function publicationYear(publication) {
    var bib = publication.bib || {};
    var year = bib.pub_year || bib.year || "";
    var parsed = parseInt(year, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
  }

  function publicationVenue(publication) {
    var bib = publication.bib || {};
    return bib.venue || bib.journal || bib.conference || bib.citation || "";
  }

  function publicationAuthors(publication) {
    var bib = publication.bib || {};
    var authors = bib.author || bib.authors || "";
    return Array.isArray(authors) ? authors.join(", ") : authors;
  }

  function publicationLink(publication) {
    return publication.eprint_url || publication.pub_url || publication.url || "";
  }

  function renderPublication(publication) {
    var bib = publication.bib || {};
    var title = bib.title || publication.title || "Untitled publication";
    var year = publicationYear(publication);
    var venue = publicationVenue(publication);
    var authors = publicationAuthors(publication);
    var citations = publication.num_citations || 0;
    var link = publicationLink(publication);
    var titleHtml = validUrl(link)
      ? '<a href="' + escapeHtml(link) + '">' + escapeHtml(title) + "</a>"
      : escapeHtml(title);
    var meta = [year || "", venue].filter(Boolean).join(" · ");

    return [
      '<div class="paper-box scholar-paper-box">',
      '<div class="paper-box-text" markdown="1">',
      "<p><strong>" + titleHtml + "</strong></p>",
      authors ? "<p>" + escapeHtml(authors) + "</p>" : "",
      meta ? "<p>" + escapeHtml(meta) + "</p>" : "",
      '<p class="scholar-paper-meta">Citations: ' + escapeHtml(citations) + "</p>",
      "</div>",
      "</div>"
    ].join("");
  }

  function renderPublications(data, container) {
    var publications = Object.keys(data.publications || {})
      .map(function (key) {
        return data.publications[key];
      })
      .filter(function (publication) {
        return publication && (publication.bib || {}).title;
      })
      .sort(function (left, right) {
        return (
          publicationYear(right) - publicationYear(left) ||
          (right.num_citations || 0) - (left.num_citations || 0)
        );
      });

    if (!publications.length) {
      return;
    }

    container.innerHTML = publications.map(renderPublication).join("");
    container.setAttribute("data-scholar-loaded", "true");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var container = document.getElementById("scholar-publications");
    if (!container) {
      return;
    }

    var source = container.getAttribute("data-scholar-source");
    if (!source) {
      return;
    }

    fetch(source, { cache: "no-cache" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Could not fetch Google Scholar publications.");
        }
        return response.json();
      })
      .then(function (data) {
        renderPublications(data, container);
      })
      .catch(function () {
        container.setAttribute("data-scholar-loaded", "false");
      });
  });
})();
