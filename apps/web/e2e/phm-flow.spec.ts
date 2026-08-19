import { expect, test } from "@playwright/test";

test("PHM can open the demonstration child", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email / staff ID").fill("phm@demo.local");
  await page.getByLabel("Password").fill("DemoPass123!");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Priority actions")).toBeVisible({ timeout: 15000 });
  await page.getByPlaceholder("Search child ID or alerts").fill("C-1042");
  await page.keyboard.press("Enter");
  await expect(page.getByText("C-1042")).toBeVisible();
});
