#!/usr/bin/env bash
# 用本模板新建一个实验项目。
#   bash tools/new_project.sh <name> [父目录]
# <name> 用小写字母、数字、- 或 _，例如 my-project；Python 包名把 - 换成 _。
# 父目录默认是当前目录。导出的是模板当前 commit 的文件，未提交的改动不会带过去。
set -euo pipefail

template="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:?用法: bash tools/new_project.sh <name> [父目录]}"
parent="${2:-.}"

if [[ ! "$name" =~ ^[a-z][a-z0-9_-]*$ ]]; then
    echo "项目名需匹配 ^[a-z][a-z0-9_-]*\$，收到: $name" >&2
    exit 1
fi
pkg="${name//-/_}"
mkdir -p "$parent"
dest="$(cd "$parent" && pwd)/$name"
if [[ -e "$dest" ]]; then
    echo "目标已存在: $dest" >&2
    exit 1
fi

# 只导出已提交的文件；生成脚本和模板仓库自己的许可证不带过去，uv.lock 在新项目里重新生成。
commit="$(git -C "$template" rev-parse --short HEAD)"
mkdir "$dest"
git -C "$template" archive --format=tar HEAD -- . ':!tools' ':!LICENSE' ':!uv.lock' | tar -x -C "$dest"

mv "$dest/src/expkit" "$dest/src/$pkg"
grep -rlI --null expkit "$dest" | xargs -0 sed -i "s/expkit/$pkg/g"
sed -i "s/^name = \"$pkg\"/name = \"$name\"/" "$dest/pyproject.toml"

cd "$dest"
git init -q
uv sync
git add -A
if git commit -qm "chore: 从 project-template@$commit 初始化 $name"; then
    echo "已创建 $dest（git commit $(git rev-parse --short HEAD)）"
else
    echo "已创建 $dest，但初次提交失败，请检查 git user.name / user.email 后手动提交" >&2
fi
echo "下一步: cd $dest && make test"
