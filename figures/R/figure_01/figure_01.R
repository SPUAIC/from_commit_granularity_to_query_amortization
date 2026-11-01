#!/usr/bin/env Rscript

# Figure 1: Experimental lifecycle of one physical run
# Dependencies: base R only.

script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) == 0) return(getwd())
  dirname(normalizePath(sub("^--file=", "", file_arg[1])))
}

draw_box <- function(x, y, w, h, label, fill, cex = 0.77) {
  rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2,
       col = fill, border = "#333333", lwd = 1.1)
  text(x, y, label, cex = cex, family = "sans")
}

draw_span <- function(x1, x2, y, label, color) {
  if (abs(x2 - x1) < 0.01) {
    x1 <- x1 - 0.045
    x2 <- x2 + 0.045
  }
  segments(x1, y, x2, y, col = color, lwd = 1.4)
  segments(x1, y, x1, y + 0.012, col = color, lwd = 1.4)
  segments(x2, y, x2, y + 0.012, col = color, lwd = 1.4)
  text((x1 + x2) / 2, y - 0.022, label, cex = 0.66, col = color)
}

draw_figure <- function() {
  nodes <- read.csv("lifecycle_nodes.csv", stringsAsFactors = FALSE)
  bounds <- read.csv("measurement_boundaries.csv", stringsAsFactors = FALSE)

  par(mar = c(0.5, 0.5, 2.2, 0.5), family = "sans")
  plot.new()
  plot.window(xlim = c(0, 1), ylim = c(0, 1), xaxs = "i", yaxs = "i")
  title("Experimental lifecycle of one physical run", font.main = 2, cex.main = 1.15)

  centers <- seq(0.075, 0.925, length.out = nrow(nodes))
  widths <- c(0.105, 0.12, 0.115, 0.125, 0.105, 0.105, 0.105)
  y <- 0.68
  h <- 0.15

  for (i in seq_len(nrow(nodes))) {
    label <- gsub("; ", "\n", nodes$label[i], fixed = TRUE)
    draw_box(centers[i], y, widths[i], h, label, nodes$fill_color[i], 0.70)
    if (i < nrow(nodes)) {
      arrows(centers[i] + widths[i] / 2 + 0.006, y,
             centers[i + 1] - widths[i + 1] / 2 - 0.006, y,
             length = 0.075, angle = 22, lwd = 1.1, col = "#404040")
    }
  }

  draw_box(0.33, 0.535, 0.07, 0.07, "Iceberg\n1.4.2", "#D9EAF7", 0.65)
  draw_box(0.41, 0.535, 0.07, 0.07, "Delta\n3.2.0", "#FCE4D6", 0.65)
  text(0.37, 0.48, "Separate campaigns on the same Spark framework",
       cex = 0.62, col = "#4D4D4D")

  draw_box(0.72, 0.535, 0.12, 0.08,
           "Iceberg\nrewrite_data_files\n+ rewrite_manifests", "#D9EAF7", 0.56)
  draw_box(0.855, 0.535, 0.095, 0.08,
           "Delta\nOPTIMIZE", "#FCE4D6", 0.62)

  text(0.025, 0.405, "Measured timing boundaries", adj = 0,
       font = 2, cex = 0.82)
  x_for_sequence <- function(s) approx(nodes$sequence, centers, xout = s)$y
  levels_y <- c("1" = 0.365, "2" = 0.315, "3" = 0.265)
  for (i in seq_len(nrow(bounds))) {
    draw_span(
      x_for_sequence(bounds$start_sequence[i]),
      x_for_sequence(bounds$end_sequence[i]),
      levels_y[as.character(bounds$level[i])],
      bounds$label[i],
      bounds$color[i]
    )
  }

  rect(0.02, 0.055, 0.98, 0.17, col = "#FAFAFA", border = "#B5B5B5")
  text(0.04, 0.178, "Independent statistical unit", adj = 0, font = 2, cex = 0.71)
  text(0.245, 0.178, "one physical ingestion run", adj = 0, cex = 0.71)
  text(0.52, 0.178, "Query executions", adj = 0, font = 2, cex = 0.71)
  text(0.64, 0.178, "technical warm-up and measurement repetitions", adj = 0, cex = 0.69)
  text(0.04, 0.12, "Run isolation", adj = 0, font = 2, cex = 0.71)
  text(0.145, 0.12, "isolated sink and checkpoint; metrics separated by exact run identifiers",
       adj = 0, cex = 0.69)
  text(0.04, 0.078, "Alignment note", adj = 0, font = 2, cex = 0.71)
  text(0.16, 0.078,
       "stored ingestion metrics follow the known n-1 alignment; terminal commit reconciled separately",
       adj = 0, cex = 0.67)
}

setwd(script_dir())
svg("figure_01_lifecycle.svg", width = 13, height = 6.5, family = "sans")
draw_figure()
dev.off()
png("figure_01_lifecycle.png", width = 3900, height = 1950, res = 300)
draw_figure()
dev.off()

cat("Created figure_01_lifecycle.svg and figure_01_lifecycle.png\n")
