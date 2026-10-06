const grid = document.querySelector("[data-posts]");

const dateFormat = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  year: "numeric",
  timeZone: "UTC",
});

function formatPostedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return dateFormat.format(date);
}

function statusMessage(text) {
  const paragraph = document.createElement("p");
  paragraph.className = "posts-status";
  paragraph.textContent = text;
  return paragraph;
}

function postCard(post) {
  const article = document.createElement("article");
  article.className = "card";

  if (post.linkedin_url) {
    article.classList.add("card-link");
    article.tabIndex = 0;
    article.setAttribute("role", "link");
    article.setAttribute("aria-label", "Open LinkedIn post");

    const openLinkedIn = () => {
      window.open(post.linkedin_url, "_blank", "noopener,noreferrer");
    };

    article.addEventListener("click", openLinkedIn);

    article.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openLinkedIn();
      }
    });
  }

  const media = document.createElement("div");
  media.className = "card-media";

  const image = document.createElement("img");
  image.src = post.image_url;
  image.alt = "";
  media.append(image);

  const body = document.createElement("div");
  body.className = "card-body";

  const time = document.createElement("time");
  time.dateTime = post.posted_at;
  time.textContent = formatPostedAt(post.posted_at);

  const content = document.createElement("p");
  content.textContent = post.content;

  body.append(time, content);
  article.append(media, body);
  return article;
}

fetch("/api/posts")
  .then((response) => {
    if (!response.ok) {
      throw new Error("Could not load posts");
    }
    return response.json();
  })
  .then((posts) => {
    if (!Array.isArray(posts) || posts.length === 0) {
      grid.replaceChildren(statusMessage("No posts yet."));
      return;
    }

    const latestFirst = posts.slice().sort((a, b) => {
      return new Date(b.posted_at) - new Date(a.posted_at);
    });
    grid.replaceChildren(...latestFirst.map(postCard));
  })
  .catch(() => {
    grid.replaceChildren(statusMessage("Posts could not be loaded."));
  });
