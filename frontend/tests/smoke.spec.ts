import {expect, test} from "@playwright/test";

test("real dashboard routes render and backend data is visible", async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", {name: "Operations overview"})).toBeVisible();
  await expect(page.getByText("Controlled research mode.")).toBeVisible();
  await page.getByRole("link", {name: /Video Workspace/}).click();
  await expect(page.getByRole("heading", {name: "Video workspace"})).toBeVisible();
  await expect(page.getByText("visionguard_demo.mp4")).toBeVisible();
  await page.getByRole("link", {name: /Semantic Search/}).click();
  await expect(page.getByRole("heading", {name: "Search visual moments"})).toBeVisible();
  await page.getByRole("link", {name: /Models & System/}).click();
  await expect(page.getByRole("heading", {name: "Models & system"})).toBeVisible();
  await expect(page.getByText(/NVIDIA GeForce|CPU fallback/)).toBeVisible();
});

