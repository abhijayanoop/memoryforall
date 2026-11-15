import { expect, test } from "vitest";

import config from "../wxt.config";

test("manifest is named memoryforall", () => {
  expect(config.manifest).toMatchObject({ name: "memoryforall" });
});
