(function () {
  var HIGHLIGHT_AUTHOR = "Mingliang Zhai";
  var PUBLICATION_IMAGES = {
    "world knowledge-enhanced reasoning using instruction-guided interactor in autonomous driving": "images/pipeline/zml-aaai-25.png",
    "fast-structext: an efficient hourglass transformer with modality-guided dynamic token merge for document understanding": "images/pipeline/zml-ijcai-23.png",
    "in-context compositional generalization for large vision-language models": "images/pipeline/lch-emnlp-24.png",
    "compositional substitutivity of visual reasoning for visual question answering": "images/pipeline/lch-eccv-24.png"
  };
  var PUBLICATION_AUTHORS = {
    "world knowledge-enhanced reasoning using instruction-guided interactor in autonomous driving": [
      "Mingliang Zhai",
      "Cheng Li",
      "Zengyuan Guo",
      "Ningrui Yang",
      "Xiameng Qin",
      "Sanyuan Zhao",
      "Junyu Han",
      "Ji Tao",
      "Yuwei Wu",
      "Yunde Jia"
    ],
    "fast-structext: an efficient hourglass transformer with modality-guided dynamic token merge for document understanding": [
      "Mingliang Zhai",
      "Yulin Li",
      "Xiameng Qin",
      "Chen Yi",
      "Qunyi Xie",
      "Chengquan Zhang",
      "Kun Yao",
      "Yuwei Wu",
      "Yunde Jia"
    ],
    "in-context compositional generalization for large vision-language models": [
      "Chuanhao Li",
      "Chenchen Jing",
      "Zhen Li",
      "Mingliang Zhai",
      "Yuwei Wu",
      "Yunde Jia"
    ],
    "compositional substitutivity of visual reasoning for visual question answering": [
      "Chuanhao Li",
      "Zhen Li",
      "Chenchen Jing",
      "Yuwei Wu",
      "Mingliang Zhai",
      "Yunde Jia"
    ]
  };
  var PUBLICATION_VENUES = {
    "world knowledge-enhanced reasoning using instruction-guided interactor in autonomous driving": "AAAI 2025",
    "fast-structext: an efficient hourglass transformer with modality-guided dynamic token merge for document understanding": "IJCAI 2023",
    "in-context compositional generalization for large vision-language models": "EMNLP 2024",
    "compositional substitutivity of visual reasoning for visual question answering": "ECCV 2024",
    "visual-guided reasoning path generation for visual question answering": "PRCV",
    "synthesizing counterfactual samples for overcoming moment biases in temporal video grounding": "PRCV"
  };

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

  function publicationVenue(publication, title) {
    var bib = publication.bib || {};
    var venue = bib.venue || bib.journal || bib.conference || bib.citation || "";
    return venue || PUBLICATION_VENUES[normalizedTitle(title)] || "Preprint";
  }

  function publicationAuthors(publication, title) {
    var bib = publication.bib || {};
    var authors = bib.author || bib.authors || "";
    if (!authors) {
      return PUBLICATION_AUTHORS[normalizedTitle(title)] || [];
    }
    if (Array.isArray(authors)) {
      return authors;
    }
    return String(authors || "")
      .split(/\s+and\s+|,\s*/i)
      .map(function (author) {
        return author.trim();
      })
      .filter(Boolean);
  }

  function publicationLink(publication) {
    return publication.eprint_url || publication.pub_url || publication.url || "";
  }

  function normalizedTitle(title) {
    return String(title || "").trim().toLowerCase().replace(/\s+/g, " ");
  }

  function publicationImage(title, generatedImages) {
    var key = normalizedTitle(title);
    return PUBLICATION_IMAGES[key] || generatedImages[key] || "";
  }

  function renderAuthors(authors) {
    return authors
      .map(function (author) {
        var escapedAuthor = escapeHtml(author);
        if (author.toLowerCase() === HIGHLIGHT_AUTHOR.toLowerCase()) {
          return '<strong class="scholar-author-highlight">' + escapedAuthor + "</strong>";
        }
        return escapedAuthor;
      })
      .join(", ");
  }

  function renderDetailItems(items) {
    var renderedItems = items
      .filter(function (item) {
        return item && item.value;
      })
      .map(function (item) {
        return '<li><span class="scholar-paper-detail-label">' + escapeHtml(item.label) + ':</span> ' + item.value + "</li>";
      });

    return renderedItems.length
      ? '<ul class="scholar-paper-details">' + renderedItems.join("") + "</ul>"
      : "";
  }

  function renderPublication(publication, generatedImages) {
    var bib = publication.bib || {};
    var title = bib.title || publication.title || "Untitled publication";
    var year = publicationYear(publication);
    var venue = publicationVenue(publication, title);
    var authors = publicationAuthors(publication, title);
    var citations = publication.num_citations || 0;
    var link = publicationLink(publication);
    var titleHtml = validUrl(link)
      ? '<a href="' + escapeHtml(link) + '">' + escapeHtml(title) + "</a>"
      : escapeHtml(title);
    var meta = [year || "", venue].filter(Boolean).join(" · ");
    var image = publicationImage(title, generatedImages);
    var details = [
      authors.length ? { label: "Authors", value: renderAuthors(authors) } : null,
      meta ? { label: "Venue", value: escapeHtml(meta) } : null,
      { label: "Citations", value: escapeHtml(citations) }
    ];

    return [
      '<div class="paper-box scholar-paper-box ' + (image ? "scholar-paper-with-image" : "scholar-paper-no-image") + '">',
      image
        ? '<div class="paper-box-image scholar-paper-image"><div><div class="badge scholar-paper-badge">' + escapeHtml(venue) + '</div><img src="' + escapeHtml(image) + '" alt="' + escapeHtml(title) + ' architecture"></div></div>'
        : "",
      '<div class="paper-box-text" markdown="1">',
      "<p><strong>" + titleHtml + "</strong></p>",
      renderDetailItems(details),
      "</div>",
      "</div>"
    ].join("");
  }

  function renderPublications(data, container, generatedImages) {
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

    container.innerHTML = publications.map(function (publication) {
      return renderPublication(publication, generatedImages);
    }).join("");
    container.setAttribute("data-scholar-loaded", "true");
  }

  function imageMapUrl(source, imagePath) {
    if (!imagePath) {
      return "";
    }
    if (validUrl(imagePath) || imagePath.charAt(0) === "/") {
      return imagePath;
    }
    return new URL(imagePath, source).toString();
  }

  function normalizeImageMap(source, imageMap) {
    return Object.keys(imageMap || {}).reduce(function (result, title) {
      result[normalizedTitle(title)] = imageMapUrl(source, imageMap[title]);
      return result;
    }, {});
  }

  function fetchJson(source, fallback) {
    if (!source) {
      return Promise.resolve(fallback);
    }

    return fetch(source, { cache: "no-cache" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Could not fetch " + source);
        }
        return response.json();
      })
      .catch(function () {
        return fallback;
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var container = document.getElementById("scholar-publications");
    if (!container) {
      return;
    }

    var source = container.getAttribute("data-scholar-source");
    var imagesSource = container.getAttribute("data-scholar-images-source");
    if (!source) {
      return;
    }

    Promise.all([
      fetchJson(source, null),
      fetchJson(imagesSource, {})
    ])
      .then(function (results) {
        if (!results[0]) {
          throw new Error("Could not fetch Google Scholar publications.");
        }
        renderPublications(results[0], container, normalizeImageMap(imagesSource, results[1]));
      })
      .catch(function () {
        container.setAttribute("data-scholar-loaded", "false");
      });
  });
})();
