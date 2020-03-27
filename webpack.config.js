const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");

module.exports = {
  mode: "development",
  entry: "./src/static/player.js",
  plugins: [
    new HtmlWebpackPlugin({
      inject: false,
      filename: "templates/blah.html",
      template: "src/static/layout.ejs"
    })
  ],
  output: {
    filename: "bundle.[contenthash].js",
    path: path.resolve(__dirname, "src/spotify_party/assets"),
    publicPath: "/assets"
  }
};
