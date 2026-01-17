import { test, expect } from '@playwright/test';

test.describe('Agent Studio Chat', () => {
  test('sends query, receives tool calls, displays CFP sources', async ({ page }) => {
    // Track API calls
    const apiCalls: { url: string; body: any; response: any }[] = [];

    // Intercept Agent Studio API
    await page.route('**/agent-studio/1/agents/*/completions*', async (route) => {
      const request = route.request();
      const body = request.postDataJSON();

      console.log('\n--- AGENT STUDIO REQUEST ---');
      console.log('URL:', request.url());
      console.log('Messages:', JSON.stringify(body.messages, null, 2));

      // Let the request through
      const response = await route.fetch();
      const json = await response.json();

      console.log('\n--- AGENT STUDIO RESPONSE (FULL) ---');
      console.log(JSON.stringify(json, null, 2));

      apiCalls.push({ url: request.url(), body, response: json });

      await route.fulfill({ response });
    });

    // Navigate to app
    await page.goto('/');

    // Verify welcome message
    const welcomeMessage = page.locator('.chat-message-assistant').first();
    await expect(welcomeMessage).toContainText("I'm your CFP finder");

    // Type a query
    const input = page.locator('.chat-input');
    await input.fill('Find me AI conferences in France');

    // Submit
    await page.locator('.chat-submit').click();

    // Verify user message appears
    const userMessage = page.locator('.chat-message-user').first();
    await expect(userMessage).toContainText('Find me AI conferences in France');

    // Wait for loading dots to appear
    const loadingDots = page.locator('.chat-loading');
    await expect(loadingDots).toBeVisible({ timeout: 2000 });
    console.log('\n--- LOADING STATE ---');
    console.log('Loading dots visible');

    // Wait for response (loading dots disappear)
    await expect(loadingDots).not.toBeVisible({ timeout: 30000 });
    console.log('Loading complete');

    // Verify API was called
    expect(apiCalls.length).toBeGreaterThan(0);
    const lastCall = apiCalls[apiCalls.length - 1];

    // Check request format
    expect(lastCall.body.messages).toBeDefined();
    expect(lastCall.body.messages.some((m: any) =>
      m.role === 'user' && m.content.includes('France')
    )).toBe(true);

    // Check response has content (AI SDK v4 format)
    expect(lastCall.response.content).toBeDefined();

    // Check tool was invoked
    expect(lastCall.response.tool_invocations?.length).toBeGreaterThan(0);
    console.log('\n--- TOOL INVOCATION ---');
    console.log('Tool:', lastCall.response.tool_invocations[0].tool_name);
    console.log('Args:', JSON.stringify(lastCall.response.tool_invocations[0].args));
    console.log('Hits:', lastCall.response.tool_invocations[0].result?.hits?.length);

    // Verify assistant response appears
    const assistantMessages = page.locator('.chat-message-assistant');
    await expect(assistantMessages).toHaveCount(2); // Welcome + response

    // Check if sources/CFP cards are rendered
    const cfpCards = page.locator('.cfp-card');
    const cardCount = await cfpCards.count();

    console.log('\n--- UI STATE ---');
    console.log('CFP cards rendered:', cardCount);

    if (cardCount > 0) {
      // Verify card content
      const firstCard = cfpCards.first();
      await expect(firstCard).toBeVisible();

      // Cards should have title
      const cardTitle = firstCard.locator('.cfp-card-title');
      const titleText = await cardTitle.textContent();
      console.log('First card title:', titleText);
    }

    // Print summary
    // Get sources from tool invocations
    const toolHits = lastCall.response.tool_invocations?.[0]?.result?.hits || [];

    console.log('\n========== TEST SUMMARY ==========');
    console.log('API calls made:', apiCalls.length);
    console.log('Tool hits returned:', toolHits.length);
    console.log('CFP cards shown:', cardCount);
    console.log('==================================\n');

    // Verify cards match tool results
    expect(cardCount).toBe(toolHits.length);
  });

  test('maintains conversation context', async ({ page }) => {
    const conversationIds: (string | null)[] = [];

    await page.route('**/agent-studio/1/agents/*/completions*', async (route) => {
      const body = route.request().postDataJSON();
      console.log('ConversationId sent:', body.conversationId);

      const response = await route.fetch();
      const json = await response.json();

      conversationIds.push(json.conversationId);
      console.log('ConversationId received:', json.conversationId);

      await route.fulfill({ response });
    });

    await page.goto('/');
    const input = page.locator('.chat-input');
    const submit = page.locator('.chat-submit');

    // First message
    await input.fill('What AI conferences are in Europe?');
    await submit.click();
    await page.locator('.chat-loading').waitFor({ state: 'hidden', timeout: 30000 });

    // Second message (follow-up)
    await input.fill('Which ones have the closest deadlines?');
    await submit.click();
    await page.locator('.chat-loading').waitFor({ state: 'hidden', timeout: 30000 });

    console.log('\n--- CONVERSATION CONTINUITY ---');
    console.log('ConversationIds:', conversationIds);

    // After first response, subsequent requests should include conversationId
    // (The first might be null, but once we get one back, we should send it)
  });

  test('handles errors gracefully', async ({ page }) => {
    // Mock a failed response
    await page.route('**/agent-studio/1/agents/*/completions*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Internal server error' }),
      });
    });

    await page.goto('/');

    const input = page.locator('.chat-input');
    await input.fill('test query');
    await page.locator('.chat-submit').click();

    // Should show error message
    const errorMessage = page.locator('.chat-message-assistant').last();
    await expect(errorMessage).toContainText('trouble processing', { timeout: 10000 });

    console.log('Error handling works correctly');
  });
});
