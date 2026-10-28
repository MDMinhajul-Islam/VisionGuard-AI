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

test("event evidence, actual video playback, overlays, and validation workflow", async ({page}) => {
  await page.goto("/review");
  await page.getByRole("button", {name: /Synthetic Fixture/}).click();
  await expect(page.getByRole("heading", {name:"Computer vision evidence viewer"})).toBeVisible();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect.poll(()=>video.evaluate(element=>(element as HTMLVideoElement).readyState)).toBeGreaterThan(0);
  await expect(page.getByAltText(/Original frame/)).toBeVisible();
  await expect(page.getByAltText(/Model overlay/)).toBeVisible();
  await expect(page.getByText("SYNTHETIC FIXTURE — NOT MODEL-GENERATED EVIDENCE")).toBeVisible();
  await page.getByRole("button", {name:"Next evidence frame"}).click();
  await page.screenshot({path:"../docs/images/phase1-5-evidence-viewer.png",fullPage:true});

  await page.getByRole("link", {name:"Validation"}).click();
  await expect(page.getByRole("heading", {name:"Validation annotations"})).toBeVisible();
  await expect(page.getByText("synthetic_generator_known_content")).toBeVisible();
  await page.getByLabel("Dataset split").selectOption("development");
  await page.getByRole("button", {name:/Evaluate predictions/}).click();
  await expect(page.getByText(/Metrics describe only this annotated local set and are not evidence of generalization/)).toBeVisible();
  await page.screenshot({path:"../docs/images/phase1-5-validation.png",fullPage:true});
});

