// 检查前端事件结构只来自 contracts；TypeScript AST 避免仅依赖命名约定。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const doc = JSON.parse(fs.readFileSync(path.join(root, "packages/api-contracts/openapi/foundation.openapi.json"), "utf8"));
const eventTypes = new Set(Object.values(doc.components.schemas).flatMap((schema) =>
  schema.properties?.type?.const ? [schema.properties.type.const] : []));

export function violations(source, fileName = "sample.ts") {
  const content = fileName.endsWith(".vue")
    ? [...source.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n")
    : source;
  const tree = ts.createSourceFile(fileName, content, ts.ScriptTarget.Latest, true);
  const errors = [];
  function visit(node) {
    if (ts.isObjectLiteralExpression(node) || ts.isTypeLiteralNode(node) || ts.isInterfaceDeclaration(node) || ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
      const members = ts.isObjectLiteralExpression(node) ? node.properties : node.members;
      const type = members.find((member) => member.name?.getText(tree).replace(/["']/g, "") === "type");
      if (type) {
        const names = new Set(members.map((member) => member.name?.getText(tree).replace(/["']/g, "")));
        const tokens = [];
        function strings(child) {
          if (ts.isStringLiteral(child)) tokens.push(child.text);
          ts.forEachChild(child, strings);
        }
        strings(type);
        if (tokens.some((token) => eventTypes.has(token)) || names.has("channel") || names.has("timestamp")) {
          const line = tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1;
          errors.push(`${fileName}:${line}: 事件结构必须从 contracts 导入`);
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return errors;
}

function files(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(directory, entry.name);
    return entry.isDirectory() ? files(full) : /\.(ts|vue)$/.test(entry.name) ? [full] : [];
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const errors = files(path.join(root, "apps/frontend/src")).flatMap((file) => violations(fs.readFileSync(file, "utf8"), file));
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else {
    console.log("前端事件合同边界检查通过");
  }
}
