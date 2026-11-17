var objGrid;
$(document).ready(function () {
    // exibeGrid();
    GRID.Init();
});


GRID = {
    Init: function () {
        if (window.location.hash) {
            var hash = jQuery.unparam(window.location.hash.substring(1));
            for (i in hash) {
                if (hash[i] && jQuery.inArray(i, ['pagina', 'limite', 'order']) == -1 && $("#" + i)) {
                    $("#" + i).val(decodeURIComponent(hash[i]));
                }
            }
        }
        GRID.Binds(true);
    },

    Binds: function (inireload) {
        objGrid = $('#conteudoPaginacao').jGrid({
            cacheUrl: false,
            tipoCorpo: "5",
            iniReload: inireload,
            url: rootUrl + 'Listar/ConsultarNoticias',
            miExcessao: "<div class='mensagem erro margin_top_20 margin_bottom_10'>Dados não encontrados</div>",
            data: {

            },
            success: function () {
                if ($(".paginacao.divisorSuperior").html() == undefined) {
                    $(".divisorSuperior").before("<div class='paginacao divisorSuperior' style='padding-bottom: 20px;'></div>");
                    $(".paginacao.divisorSuperior").append($(".paginacao .controle").first());
                } else {
                    $(".paginacao.divisorSuperior").html("");
                    $(".paginacao.divisorSuperior").append($(".paginacao .controle").first());

                }
                if ($(".paginacao.divisorInferior").html() == undefined) {
                    $(".divisorInferior").before("<div class='paginacao divisorInferior' style='padding-bottom: 20px;'></div>");
                    $(".paginacao.divisorInferior").append($(".paginacao .controle").last());
                }
                else {
                    $(".paginacao.divisorInferior").html("");
                    $(".paginacao.divisorInferior").append($(".paginacao .controle").last());

                }
            }
        });
    }
}

