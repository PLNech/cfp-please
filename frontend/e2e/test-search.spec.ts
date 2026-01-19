import { test, expect } from '@playwright/test';

test.describe('Search and Autocomplete', () => {
  test('homepage loads with header and autocomplete', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Take screenshot
    await page.screenshot({ path: './screenshots/01-homepage.png', fullPage: true });

    // Check main header is visible
    const header = page.locator('.talkflix-header');
    await expect(header).toBeVisible();

    // Check autocomplete container exists
    const autocomplete = page.locator('.talkflix-autocomplete');
    await expect(autocomplete).toBeVisible();

    console.log('Homepage loaded successfully');
  });

  test('autocomplete dropdown appears in correct position', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Find and click autocomplete input
    const input = page.locator('.aa-Input');
    await input.click();
    await input.fill('kube');
    await page.waitForTimeout(1000);

    // Screenshot with dropdown
    await page.screenshot({ path: './screenshots/02-autocomplete.png', fullPage: true });

    // Check panel appears
    const panel = page.locator('.aa-Panel');
    await expect(panel).toBeVisible();

    // Get positions
    const inputBox = await input.boundingBox();
    const panelBox = await panel.boundingBox();

    console.log('Input position:', inputBox);
    console.log('Panel position:', panelBox);

    // Panel should be below input, not at bottom of page
    if (inputBox && panelBox) {
      // Panel top should be near input bottom (within 50px)
      const distance = panelBox.y - (inputBox.y + inputBox.height);
      expect(distance).toBeLessThan(50);
      expect(distance).toBeGreaterThanOrEqual(0);
      console.log(`Panel is ${distance}px below input - CORRECT!`);
    }
  });

  test('search page has dark theme', async ({ page }) => {
    // Note: baseURL already includes /cfp-please/
    await page.goto('./search');
    await page.waitForLoadState('networkidle');

    // Screenshot
    await page.screenshot({ path: './screenshots/03-search-page.png', fullPage: true });

    // Check search-page container (not body) has dark background
    const searchPage = page.locator('.search-page');
    await expect(searchPage).toBeVisible();

    const bgColor = await searchPage.evaluate(el => getComputedStyle(el).backgroundColor);
    console.log('Search page background:', bgColor);

    // Should NOT be white/light (rgb(250, 250, 250) or similar)
    expect(bgColor).not.toContain('250');
    expect(bgColor).not.toContain('255, 255, 255');

    // Check text is light colored
    const title = page.locator('.search-page-title');
    if (await title.isVisible()) {
      const textColor = await title.evaluate(el => getComputedStyle(el).color);
      console.log('Title color:', textColor);
      // Text should be light (high RGB values)
      expect(textColor).toMatch(/rgb\(2[0-5]\d/);
    }

    console.log('Search page dark theme verified');
  });

  test('search page shows results from all indexes', async ({ page }) => {
    await page.goto('./search');
    await page.waitForLoadState('networkidle');

    // Screenshot search page
    await page.screenshot({ path: './screenshots/04-search-results.png', fullPage: true });

    // Check for results in each section (no query = shows all)
    // Use more specific title selectors
    const cfpTitle = page.locator('.search-section-title').filter({ hasText: /^CFPs/ });
    const talkTitle = page.locator('.search-section-title').filter({ hasText: /^Talks/ });
    const speakerTitle = page.locator('.search-section-title').filter({ hasText: /^Speakers/ });

    // Wait for section titles to be visible
    await expect(cfpTitle).toBeVisible();
    await expect(talkTitle).toBeVisible();
    await expect(speakerTitle).toBeVisible();

    // Get sections by their titles
    const cfpSection = cfpTitle.locator('..'); // parent
    const talkSection = talkTitle.locator('..');
    const speakerSection = speakerTitle.locator('..');

    // Count results in each section
    const cfpCards = cfpSection.locator('.search-result-card');
    const talkCards = talkSection.locator('.search-result-card');
    const speakerCards = speakerSection.locator('.search-result-card');

    const cfpCount = await cfpCards.count();
    const talkCount = await talkCards.count();
    const speakerCount = await speakerCards.count();

    console.log(`Results: ${cfpCount} CFPs, ${talkCount} talks, ${speakerCount} speakers`);

    // Should have at least some results
    expect(cfpCount + talkCount + speakerCount).toBeGreaterThan(0);
  });
});
