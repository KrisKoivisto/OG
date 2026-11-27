# Stockroom

Inventory app for flipping sneakers and electronics. Lives here as a stopgap. It isn't part of the podcast toolkit and should move to its own repo.

- The app: https://claude.ai/artifact/JdjDaiRSDGZEdjmAjGL7LZ
- Source: `index.html` (one file, published as a Claude artifact)

What it does:

- Add an item from photos. Claude names it, writes the listing, lists the wear, and guesses a price range.
- Tracks asking price, lowest price, what you paid, where it's posted, how long it's been up, and what it sold for.
- Per site: open the site's new-listing page, copy the title and listing text, tick "posted".
- Heat tab: what's in demand and what's a brick. Claude refreshes it weekly from the web.

Data lives in the artifact's own database (`items`, `trends/current`, `config/app`) and photos in its file storage. Only the owner and editors can read it.

Fees in the Sites tab were checked Nov 25, 2026.
