import {expect, test} from "@playwright/test";

test("real dashboard routes render and backend data is visible", async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", {name: "Operations overview"})).toBeVisible();
  await expect(page.getByText("Controlled research mode.")).toBeVisible();
  await page.getByRole("link", {name: /Video Workspace/}).click();
  await expect(page.getByRole("heading", {name: "Video workspace"})).toBeVisible();
  await expect(page.getByRole("heading", {name:"Local video library"})).toBeVisible();
  await page.getByRole("link", {name: /Semantic Search/}).click();
  await expect(page.getByRole("heading", {name: "Search visual moments"})).toBeVisible();
  await page.getByRole("link", {name: /Models & System/}).click();
  await expect(page.getByRole("heading", {name: "Models & system"})).toBeVisible();
  await expect(page.getByText(/NVIDIA GeForce|CPU fallback/)).toBeVisible();
});

test("real imported video playback and model-result inspection", async ({page}) => {
  test.setTimeout(60_000);
  const assetsResponse=page.waitForResponse(response=>response.url().endsWith("/api/datasets/assets"));
  await page.goto("/datasets");
  expect((await assetsResponse).ok()).toBeTruthy();
  await expect(page.getByRole("heading", {name:"Dataset evaluation"})).toBeVisible();
  await page.getByRole("button", {name:"fall-02"}).click();
  await expect(page.getByRole("heading", {name:"fall-02"})).toBeVisible();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect.poll(()=>video.evaluate(element=>(element as HTMLVideoElement).readyState)).toBeGreaterThan(0);
  await expect(page.getByText("Candidate", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("source frame labels", {exact:true}).last()).toBeVisible();
  await page.getByRole("button", {name:"fall-18"}).click();
  await expect(page.getByRole("heading", {name:"Fall diagnostic evidence"})).toBeVisible();
  await expect(page.getByRole("button", {name:/Torso orientation/})).toBeVisible();
  await expect(page.getByText(/Improved replay/).first()).toBeVisible();
  await page.screenshot({path:"../data/external/validation/reports/fall18-diagnostics-dashboard.png",fullPage:true});
});

test("dataset evaluation workspace separates provenance and predictions", async ({page}) => {
  const evaluationResponse=page.waitForResponse(response=>response.url().includes("/api/datasets/evaluation"));
  await page.goto("/datasets");
  expect((await evaluationResponse).ok()).toBeTruthy();
  await expect(page.getByRole("heading", {name:"Dataset evaluation"})).toBeVisible();
  await expect(page.getByRole("heading", {name:"Preserved baseline"})).toBeVisible();
  await expect(page.getByText(/Event-level metrics require verified temporal annotations/)).toBeVisible();
  await expect(page.getByText("80.0%", {exact:true})).toBeVisible();
  await expect(page.getByText("40.0%", {exact:true})).toBeVisible();
  await expect(page.getByText("53.3%", {exact:true})).toBeVisible();
  await page.screenshot({path:"../data/external/validation/reports/dataset-evaluation-dashboard.png"});
});

