import flet as ft
import banco
from datetime import datetime
import json
import os

# ==========================================
# GERENCIADOR DE ACESSO LOCAL
# ==========================================
ARQUIVO_CONFIG = "config_acesso.json"

def salvar_acesso(usuario, senha):
    try:
        with open(ARQUIVO_CONFIG, 'w') as f:
            json.dump({"user": usuario, "pass": senha}, f)
    except Exception:
        pass

def ler_acesso():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r') as f:
                dados = json.load(f)
                return dados.get("user"), dados.get("pass")
        except Exception:
            return None, None
    return None, None

def limpar_acesso():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            os.remove(ARQUIVO_CONFIG)
        except Exception:
            pass

def main(page: ft.Page):
    # ==========================================
    # CONFIGURAÇÕES BASE
    # ==========================================
    page.title = "Meu Ateliê"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 700

    def show_snack(msg, is_success=True):
        cor = ft.Colors.GREEN_800 if is_success else ft.Colors.RED_800
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=cor)
        page.snack_bar.open = True
        page.update()

    # ==========================================
    # APP PRINCIPAL DA ARTESÃ
    # ==========================================
    def construir_app_principal():
        area_conteudo = ft.Container(expand=True, alignment=ft.Alignment.TOP_CENTER, padding=20)

        def sair_da_conta(e):
            limpar_acesso()
            page.appbar = None
            page.clean()
            renderizar_login()

        page.appbar = ft.AppBar(
            title=ft.Text("Meu Ateliê", weight="bold"),
            bgcolor=ft.Colors.PURPLE_900
        )

        col_fornecedores = ft.Column(scroll="auto", expand=True)
        col_materiais = ft.Column(scroll="auto", expand=True)
        col_categorias = ft.Column(scroll="auto", expand=True)
        col_historico = ft.Column(scroll="auto", expand=True)
        
        # Elementos do Dashboard (Início)
        txt_gasto_mes = ft.Text("R$ 0,00", size=32, weight="bold", color=ft.Colors.WHITE)
        col_resultados_busca_rapida = ft.Column(spacing=2) 
        col_lista_faltas = ft.Column(spacing=5)
        inp_nova_falta = ft.TextField(label="Ex: Fita Gorgurão Azul", height=45, text_size=14, expand=True)

        def adicionar_falta(e=None):
            val = inp_nova_falta.value.strip()
            if val:
                banco.adicionar_item_falta(val)
                inp_nova_falta.value = ""
                atualizar_lista_faltas()
                page.update()
        
        inp_nova_falta.on_submit = adicionar_falta
        row_add_falta = ft.Row([
            inp_nova_falta, 
            ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="purple", icon_size=40, on_click=adicionar_falta)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        def concluir_falta(id_item):
            banco.remover_item_falta(id_item)
            atualizar_lista_faltas()
            show_snack("Item comprado e removido da lista!")

        def atualizar_lista_faltas():
            col_lista_faltas.controls.clear()
            itens = banco.listar_itens_falta()
            if not itens:
                col_lista_faltas.controls.append(ft.Text("Lista vazia. Tudo em dia! 🎉", color="gray", size=14))
            else:
                for item in itens:
                    id_i, nome_i = item
                    col_lista_faltas.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SHOPPING_CART_OUTLINED, color="gray", size=18),
                                ft.Text(nome_i, expand=True, size=14, weight="bold"),
                                ft.IconButton(ft.Icons.CHECK_CIRCLE_OUTLINE, icon_color="green", tooltip="Marcar como comprado", on_click=lambda e, i=id_i: concluir_falta(i))
                            ]),
                            bgcolor=ft.Colors.BLUE_GREY_800, padding=ft.Padding(10, 0, 10, 0), border_radius=8
                        )
                    )

        # ==========================================
        # ATUALIZAÇÃO GERAL (TELA INÍCIO E HISTÓRICO)
        # ==========================================
        def atualizar_dashboard_e_historico():
            gasto = banco.calcular_gasto_mes_atual()
            txt_gasto_mes.value = f"R$ {gasto:.2f}"
            atualizar_lista_faltas()

            col_historico.controls.clear()
            compras = banco.listar_historico_compras()
            
            if not compras:
                col_historico.controls.append(ft.Container(content=ft.Text("Nenhuma compra registada ainda.", color="gray"), padding=20))
            else:
                for c in compras:
                    id_c, data, mat_nome, loja_nome, qtd, total, unitario, unidade, mat_id, loja_id = c
                    data_formatada = data.strftime('%d/%m/%Y') if not isinstance(data, str) else data
                    loja_f = loja_nome if loja_nome else "Fornecedor Excluído"
                    
                    item_hist = ft.ListTile(
                        leading=ft.Icon(ft.Icons.SHOPPING_BAG, color=ft.Colors.PURPLE_400),
                        title=ft.Text(mat_nome if mat_nome else "Excluído", weight="bold"),
                        subtitle=ft.Text(f"{loja_f}\n{data_formatada} • Comprado: {qtd} {unidade}", size=12, color="gray"),
                        trailing=ft.Row([
                            ft.Column([
                                ft.Text(f"Total: R$ {total:.2f}", size=12, color="gray"),
                                ft.Text(f"R$ {unitario:.2f} / {unidade[:3]}.", weight="bold", color=ft.Colors.GREEN_400)
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END, tight=True),
                            ft.IconButton(ft.Icons.EDIT, icon_color="gray", on_click=lambda e, i=id_c, d=data, m=mat_id, l=loja_id, q=qtd, t=total: abrir_edicao_compra(i, d, m, l, q, t))
                        ], tight=True, alignment=ft.MainAxisAlignment.END)
                    )
                    col_historico.controls.append(item_hist)
            page.update()

        # ==========================================
        # EDIÇÃO DE COMPRA DO HISTÓRICO (Com Filtro de Busca)
        # ==========================================
        def abrir_edicao_compra(id_c, data_compra, mat_id, loja_id, qtd, total, bs_pai=None):
            if bs_pai:
                bs_pai.open = False
                page.update()

            materiais = banco.listar_materiais()
            lojas = banco.listar_fornecedores()
            data_f = data_compra.strftime('%d/%m/%Y') if not isinstance(data_compra, str) else data_compra

            dp_mat = ft.Dropdown(label="Selecione na lista...", options=[ft.dropdown.Option(key=str(m[0]), text=m[1]) for m in materiais], value=str(mat_id) if mat_id else None, width=320)
            
            # FILTRO EM TEMPO REAL
            def filtrar_mat_edit(e_filter):
                busca = e_filter.control.value.lower()
                dp_mat.options = [ft.dropdown.Option(key=str(m[0]), text=m[1]) for m in materiais if busca in m[1].lower()]
                if dp_mat.options:
                    dp_mat.value = dp_mat.options[0].key
                else:
                    dp_mat.value = None
                page.update()

            inp_busca_mat = ft.TextField(label="🔍 Buscar material na lista...", on_change=filtrar_mat_edit, width=320, height=45, text_size=14, border_radius=8)
            
            dp_loja = ft.Dropdown(label="Onde Comprou?", options=[ft.dropdown.Option(key=str(l[0]), text=l[1]) for l in lojas], value=str(loja_id) if loja_id else None, width=320)
            inp_qtd = ft.TextField(label="Quantidade", value=str(qtd), width=320, keyboard_type=ft.KeyboardType.NUMBER)
            inp_valor = ft.TextField(label="Valor Total (R$)", value=f"{total:.2f}", width=320, keyboard_type=ft.KeyboardType.NUMBER)
            inp_data = ft.TextField(label="Data (DD/MM/AAAA)", value=data_f, width=320)

            def salvar(e):
                if getattr(btn_salvar, 'disabled', False): return
                btn_salvar.disabled = True
                btn_salvar.content = ft.ProgressRing(width=20, height=20, color="white", stroke_width=2)
                page.update()

                try:
                    if not dp_mat.value or not dp_loja.value:
                        show_snack("Selecione material e loja válidos.", False)
                        return
                    
                    data_db = datetime.strptime(inp_data.value.strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
                    v_total = inp_valor.value.replace(',', '.')
                    v_qtd = inp_qtd.value.replace(',', '.') if inp_qtd.value else "1"
                    
                    suc, msg = banco.editar_compra_material(id_c, data_db, int(dp_mat.value), int(dp_loja.value), v_qtd, v_total)
                    if suc:
                        bs_edit.open = False
                        atualizar_dashboard_e_historico()
                        atualizar_lista_materiais()
                        show_snack("Compra atualizada com sucesso!")
                    else:
                        show_snack(msg, False)
                except Exception:
                    show_snack("Verifique a data e os valores", False)
                finally:
                    if bs_edit.open:
                        btn_salvar.disabled = False
                        btn_salvar.content = ft.Text("SALVAR", color="white", weight="bold")
                        page.update()

            def excluir(e):
                suc, msg = banco.deletar_compra_material(id_c)
                if suc:
                    bs_edit.open = False
                    atualizar_dashboard_e_historico()
                    atualizar_lista_materiais()
                    show_snack("Registo excluído!")
                else:
                    show_snack(msg, False)

            btn_salvar = ft.Container(content=ft.Text("SALVAR", color="white", weight="bold"), bgcolor=ft.Colors.TEAL_600, width=320, height=50, border_radius=8, alignment=ft.Alignment.CENTER, ink=True, on_click=salvar)
            btn_excluir = ft.Container(content=ft.Text("EXCLUIR REGISTO", color="white", weight="bold"), bgcolor=ft.Colors.RED_700, width=320, height=50, border_radius=8, alignment=ft.Alignment.CENTER, ink=True, on_click=excluir)
            
            bs_edit = ft.BottomSheet(
                ft.Container(padding=20, bgcolor=ft.Colors.BLUE_GREY_900, content=ft.Column([
                    ft.Text("Editar ou Excluir Compra", size=20, weight="bold", color="purple"), 
                    inp_data, inp_busca_mat, dp_mat, dp_loja, inp_qtd, inp_valor, 
                    ft.Container(height=10), btn_salvar, ft.Container(height=5), btn_excluir, ft.Container(height=20)
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll="auto"))
            )
            page.overlay.append(bs_edit)
            bs_edit.open = True
            page.update()

        # ==========================================
        # GESTÃO: EDIÇÃO AVANÇADA (NOME, CATEGORIA E MEDIDA)
        # ==========================================
        def abrir_edicao_gestao(tipo, id_item, nome_antigo, cat_id_antiga=None, medida_antiga=None):
            inp_nome = ft.TextField(label="Novo Nome", value=nome_antigo)
            
            controles_edicao = [inp_nome]
            dp_cat = None
            dp_medida = None

            if tipo == 'MATERIAL':
                cats = banco.listar_categorias_por_tipo('SAIDA')
                dp_cat = ft.Dropdown(
                    label="Categoria", 
                    options=[ft.dropdown.Option(key=str(c[0]), text=c[1]) for c in cats], 
                    value=str(cat_id_antiga) if cat_id_antiga else None
                )
                dp_medida = ft.Dropdown(
                    label="Comprado por", 
                    options=[
                        ft.dropdown.Option("Metros"), 
                        ft.dropdown.Option("Unidades"), 
                        ft.dropdown.Option("Gramas"),
                        ft.dropdown.Option("Pacotes")
                    ], 
                    value=medida_antiga if medida_antiga else "Metros"
                )
                controles_edicao.extend([dp_cat, dp_medida])

            def salvar_edicao(e):
                novo = inp_nome.value.strip()
                if novo:
                    if tipo == 'FORNECEDOR': 
                        banco.editar_fornecedor(id_item, novo)
                    elif tipo == 'CATEGORIA': 
                        banco.editar_categoria(id_item, novo)
                    elif tipo == 'MATERIAL': 
                        if dp_cat and dp_cat.value and dp_medida and dp_medida.value:
                            banco.editar_material(id_item, novo, int(dp_cat.value), dp_medida.value)
                        else:
                            show_snack("Preencha categoria e medida!", False)
                            return
                            
                dlg_edicao.open = False
                atualizar_gestao()
                atualizar_dashboard_e_historico()
                show_snack("Atualizado com sucesso!")

            def excluir_item(e):
                if tipo == 'FORNECEDOR': banco.deletar_fornecedor(id_item)
                elif tipo == 'CATEGORIA': banco.deletar_categoria(id_item)
                elif tipo == 'MATERIAL': banco.deletar_material(id_item)
                
                dlg_edicao.open = False
                atualizar_gestao()
                atualizar_dashboard_e_historico()
                show_snack("Excluído com sucesso!")

            dlg_edicao = ft.AlertDialog(
                title=ft.Text("Editar ou Excluir"), 
                content=ft.Column(controles_edicao, tight=True),
                actions=[
                    ft.TextButton("Excluir", on_click=excluir_item, style=ft.ButtonStyle(color=ft.Colors.RED)),
                    ft.TextButton("Salvar", on_click=salvar_edicao)
                ], actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
            page.overlay.append(dlg_edicao)
            dlg_edicao.open = True
            page.update()

        def abrir_detalhes_material(mat):
            # mat agora traz 5 campos: id, nome, medida, categoria_nome, categoria_id
            id_m, nome, medida, categoria_nome, cat_id = mat
            historico = banco.listar_historico_por_material(id_m)
            col_hist_detalhe = ft.Column(scroll="auto", height=350)
            bs_detalhes = ft.BottomSheet(ft.Container()) 

            inp_busca_rapida.value = ""
            col_resultados_busca_rapida.controls.clear()

            if not historico:
                col_hist_detalhe.controls.append(ft.Container(content=ft.Text("Nenhuma compra registada para este material.", color="gray"), padding=20))
            else:
                for h in historico:
                    id_c, data_c, loja, qtd, total, unit, loja_id = h
                    data_f = data_c.strftime('%d/%m/%Y') if not isinstance(data_c, str) else data_c
                    loja_f = loja if loja else "Fornecedor Excluído"
                    
                    col_hist_detalhe.controls.append(
                        ft.Container(
                            bgcolor=ft.Colors.BLUE_GREY_800, padding=15, border_radius=8, margin=ft.Margin.only(bottom=5),
                            content=ft.Column([
                                ft.Row([
                                    ft.Text(data_f, weight="bold"),
                                    ft.Row([
                                        ft.Text(f"R$ {unit:.2f} / {medida[:3]}.", weight="bold", color=ft.Colors.GREEN_400),
                                        ft.IconButton(ft.Icons.EDIT, icon_color="gray", icon_size=18, on_click=lambda e, i=id_c, d=data_c, l=loja_id, q=qtd, t=total: abrir_edicao_compra(i, d, id_m, l, q, t, bs_pai=bs_detalhes))
                                    ])
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Loja: {loja_f}", size=12, color="orange"),
                                ft.Text(f"Comprado: {qtd} {medida} | Total: R$ {total:.2f}", size=12, color="gray")
                            ])
                        )
                    )
            
            bs_detalhes.content = ft.Container(
                padding=20, bgcolor=ft.Colors.BLUE_GREY_900,
                content=ft.Column([
                    ft.Text(nome, size=20, weight="bold", color="purple"),
                    ft.Text(f"Categoria: {categoria_nome}", size=12, color="gray"),
                    ft.Divider(),
                    ft.Text("Histórico de Preços deste Item:", weight="bold"),
                    ft.Container(height=5),
                    col_hist_detalhe,
                    ft.Container(height=20)
                ], tight=True)
            )
            page.overlay.append(bs_detalhes)
            bs_detalhes.open = True
            page.update()

        def atualizar_lista_materiais(busca=""):
            col_materiais.controls.clear()
            materiais = banco.listar_materiais()
            if busca:
                materiais = [m for m in materiais if busca.lower() in m[1].lower()]
            for m in materiais:
                col_materiais.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.BRUSH, color="purple"), title=ft.Text(m[1]), 
                        subtitle=ft.Text(f"Categoria: {m[3]} | Medida: {m[2]}", color="gray", size=12), 
                        # Aqui chamamos a edição passando todos os dados do material (ID, Nome, Categoria_ID, Medida)
                        trailing=ft.IconButton(ft.Icons.EDIT, icon_color="gray", tooltip="Editar Detalhes", on_click=lambda e, id_m=m[0], n=m[1], m_medida=m[2], m_cat_id=m[4]: abrir_edicao_gestao('MATERIAL', id_m, n, m_cat_id, m_medida)),
                        on_click=lambda e, mat=m: abrir_detalhes_material(mat)
                    )
                )
            page.update()

        def atualizar_gestao():
            col_fornecedores.controls.clear()
            col_categorias.controls.clear()

            for f in banco.listar_fornecedores():
                col_fornecedores.controls.append(ft.ListTile(leading=ft.Icon(ft.Icons.STORE, color="orange"), title=ft.Text(f[1]), trailing=ft.IconButton(ft.Icons.EDIT, icon_color="gray", on_click=lambda e, id_f=f[0], n=f[1]: abrir_edicao_gestao('FORNECEDOR', id_f, n))))
            for c in banco.listar_categorias_por_tipo('SAIDA'):
                col_categorias.controls.append(ft.ListTile(leading=ft.Icon(ft.Icons.CATEGORY, color="blue"), title=ft.Text(c[1]), trailing=ft.IconButton(ft.Icons.EDIT, icon_color="gray", on_click=lambda e, id_c=c[0], n=c[1]: abrir_edicao_gestao('CATEGORIA', id_c, n))))
            
            atualizar_lista_materiais() 
            page.update()

        inp_busca_material = ft.TextField(label="Buscar material...", prefix_icon=ft.Icons.SEARCH, height=40, text_size=14, on_change=lambda e: atualizar_lista_materiais(e.control.value))

        def abrir_novo_fornecedor(e):
            inp_nome = ft.TextField(label="Nome da Loja")
            def salvar(e):
                if banco.adicionar_fornecedor(inp_nome.value)[0]:
                    dlg.open = False
                    atualizar_gestao()
                    show_snack("Loja salva!")
            dlg = ft.AlertDialog(title=ft.Text("Nova Loja"), content=inp_nome, actions=[ft.TextButton("Salvar", on_click=salvar)])
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        def abrir_novo_material(e):
            inp_nome = ft.TextField(label="Nome do Material (Ex: Fita Gorgurão 38mm)")
            dp_medida = ft.Dropdown(
                label="Comprado por", 
                options=[
                    ft.dropdown.Option("Metros"), 
                    ft.dropdown.Option("Unidades"), 
                    ft.dropdown.Option("Gramas"),
                    ft.dropdown.Option("Pacotes") 
                ], 
                value="Metros"
            )
            cats = banco.listar_categorias_por_tipo('SAIDA')
            if not cats: 
                show_snack("Crie uma categoria primeiro na aba Gestão!", False)
                return
            dp_cat = ft.Dropdown(label="Categoria", options=[ft.dropdown.Option(key=str(c[0]), text=c[1]) for c in cats], value=str(cats[0][0]))

            def salvar(e):
                if banco.adicionar_material(inp_nome.value, int(dp_cat.value), dp_medida.value)[0]:
                    dlg.open = False
                    atualizar_gestao()
                    show_snack("Material salvo!")
            dlg = ft.AlertDialog(title=ft.Text("Novo Material"), content=ft.Column([inp_nome, dp_cat, dp_medida], tight=True), actions=[ft.TextButton("Salvar", on_click=salvar)])
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        def abrir_nova_categoria(e):
            inp_nome = ft.TextField(label="Nome da Categoria (Ex: FITAS)")
            def salvar(e):
                if banco.adicionar_categoria(inp_nome.value, 'SAIDA')[0]:
                    dlg.open = False
                    atualizar_gestao()
                    show_snack("Categoria salva!")
            dlg = ft.AlertDialog(title=ft.Text("Nova Categoria"), content=inp_nome, actions=[ft.TextButton("Salvar", on_click=salvar)])
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        btn_add_material = ft.Container(content=ft.Text("+ Adicionar Material", color="white", weight="bold"), bgcolor=ft.Colors.PURPLE_700, padding=10, border_radius=8, ink=True, on_click=abrir_novo_material, alignment=ft.Alignment.CENTER)
        btn_add_loja = ft.Container(content=ft.Text("+ Adicionar Loja", color="white", weight="bold"), bgcolor=ft.Colors.ORANGE_700, padding=10, border_radius=8, ink=True, on_click=abrir_novo_fornecedor, alignment=ft.Alignment.CENTER)
        btn_add_cat = ft.Container(content=ft.Text("+ Adicionar Categoria", color="white", weight="bold"), bgcolor=ft.Colors.BLUE_700, padding=10, border_radius=8, ink=True, on_click=abrir_nova_categoria, alignment=ft.Alignment.CENTER)

        tela_gestao = ft.Tabs(
            length=3, selected_index=0,
            content=ft.Column([
                ft.TabBar(tabs=[ft.Tab(label="Materiais"), ft.Tab(label="Lojas"), ft.Tab(label="Categorias")]),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Column([ft.Container(height=5), btn_add_material, inp_busca_material, col_materiais], scroll="auto"),
                        ft.Column([ft.Container(height=5), btn_add_loja, col_fornecedores], scroll="auto"),
                        ft.Column([ft.Container(height=5), btn_add_cat, col_categorias], scroll="auto")
                    ]
                )
            ], expand=True)
        )

        tela_historico = ft.Column([
            ft.Text("Histórico de Preços", size=24, weight="bold"),
            ft.Text("Acompanhe a variação do custo dos seus materiais", size=14, color="gray"),
            ft.Container(height=10), col_historico
        ], expand=True)

        # ==========================================
        # DASHBOARD INICIAL (E COMPRA COM FILTRO)
        # ==========================================
        def realizar_busca_rapida(e):
            col_resultados_busca_rapida.controls.clear()
            busca = e.control.value.strip().lower()
            
            if not busca:
                page.update()
                return

            materiais = banco.listar_materiais()
            resultados = [m for m in materiais if busca in m[1].lower()]

            if not resultados:
                col_resultados_busca_rapida.controls.append(ft.Text("Nenhum material encontrado.", color="gray", size=12))
            else:
                for m in resultados[:3]:
                    col_resultados_busca_rapida.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.SEARCH, color="purple", size=20),
                            title=ft.Text(m[1], size=14, weight="bold"),
                            subtitle=ft.Text(f"Categoria: {m[3]}", size=12, color="gray"),
                            on_click=lambda e, mat=m: abrir_detalhes_material(mat),
                            content_padding=ft.Padding(0, 0, 0, 0)
                        )
                    )
            page.update()

        inp_busca_rapida = ft.TextField(
            label="Consultar preço de um material...", prefix_icon=ft.Icons.SEARCH,
            height=45, text_size=14, border_radius=8, on_change=realizar_busca_rapida
        )

        def abrir_compra(e):
            materiais = banco.listar_materiais()
            lojas = banco.listar_fornecedores()

            if not materiais or not lojas:
                show_snack("Cadastre 1 Material e 1 Loja na aba Gestão!", False)
                return

            dp_mat = ft.Dropdown(label="Selecione na lista...", options=[ft.dropdown.Option(key=str(m[0]), text=m[1]) for m in materiais], width=320)
            if materiais: dp_mat.value = str(materiais[0][0])
            
            # FILTRO EM TEMPO REAL
            def filtrar_mat(e_filter):
                busca = e_filter.control.value.lower()
                dp_mat.options = [ft.dropdown.Option(key=str(m[0]), text=m[1]) for m in materiais if busca in m[1].lower()]
                if dp_mat.options:
                    dp_mat.value = dp_mat.options[0].key
                else:
                    dp_mat.value = None
                page.update()

            inp_busca_mat = ft.TextField(label="🔍 Buscar material na lista...", on_change=filtrar_mat, width=320, height=45, text_size=14, border_radius=8)

            dp_loja = ft.Dropdown(label="Onde comprou?", options=[ft.dropdown.Option(key=str(l[0]), text=l[1]) for l in lojas], value=str(lojas[0][0]), width=320)
            inp_qtd = ft.TextField(label="Quantidade (Opcional)", width=320, keyboard_type=ft.KeyboardType.NUMBER)
            inp_valor = ft.TextField(label="Valor Total Pago (R$)", width=320, keyboard_type=ft.KeyboardType.NUMBER)

            def salvar_compra(e_salvar):
                if getattr(btn_salvar, 'disabled', False): return
                btn_salvar.disabled = True
                btn_salvar.content = ft.ProgressRing(width=20, height=20, color="white", stroke_width=2)
                page.update()
                
                try:
                    if not dp_mat.value or not dp_loja.value:
                        show_snack("Selecione material e loja válidos.", False)
                        return

                    data_hoje = datetime.today().strftime('%Y-%m-%d')
                    v_total = inp_valor.value.replace(',', '.')
                    v_qtd = inp_qtd.value.replace(',', '.') if inp_qtd.value else "1"
                    
                    suc, msg = banco.registrar_compra_material(data_hoje, int(dp_mat.value), int(dp_loja.value), v_qtd, v_total, "Caixa")
                    if suc:
                        bs_compra.open = False
                        atualizar_dashboard_e_historico()
                        show_snack(msg)
                    else:
                        show_snack(msg, False)
                except Exception:
                    show_snack("Erro ao processar dados numéricos", False)
                finally:
                    if bs_compra.open:
                        btn_salvar.disabled = False
                        btn_salvar.content = ft.Text("REGISTAR COMPRA", color="white", weight="bold")
                        page.update()

            btn_salvar = ft.Container(content=ft.Text("REGISTAR COMPRA", color="white", weight="bold"), bgcolor="purple", width=320, height=50, border_radius=8, alignment=ft.Alignment.CENTER, ink=True, on_click=salvar_compra)
            
            bs_compra = ft.BottomSheet(
                ft.Container(padding=20, bgcolor=ft.Colors.BLUE_GREY_900, content=ft.Column([
                    ft.Text("Nova Compra de Material", size=20, weight="bold", color="purple"), 
                    inp_busca_mat, dp_mat, dp_loja, inp_qtd, inp_valor, 
                    ft.Container(height=10), btn_salvar, ft.Container(height=20)
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll="auto"))
            )
            page.overlay.append(bs_compra)
            bs_compra.open = True
            page.update()

        card_gasto = ft.Container(
            content=ft.Column([
                ft.Text("Gasto em Materiais (Este Mês)", size=12, weight="bold", color=ft.Colors.GREY_400),
                txt_gasto_mes
            ]), bgcolor=ft.Colors.BLUE_GREY_900, padding=20, border_radius=15, width=350
        )

        tela_inicio = ft.Column([
            ft.Container(height=10),
            ft.Row([ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON)), ft.Text(f"Olá, {banco.USUARIO_NOME}!", size=22, weight="bold")]),
            ft.Container(height=10),
            card_gasto,
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.SHOPPING_BAG, size=40, color="white"),
                    ft.Text("Registar Compra de Material", color="white", weight="bold", size=16)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=ft.Colors.PURPLE_700, padding=20, border_radius=15, ink=True, on_click=abrir_compra, width=350, height=120
            ),
            ft.Container(height=5),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, color="white", size=18),
                    ft.Text("Cadastrar Novo Material", color="white", weight="bold", size=14)
                ], alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=ft.Colors.PURPLE_900, padding=10, border_radius=10, ink=True, on_click=abrir_novo_material, width=350
            ),
            ft.Container(height=20),
            inp_busca_rapida,
            col_resultados_busca_rapida,
            ft.Divider(height=20, color="transparent"),
            ft.Text("Lista de Compras (Faltas):", size=14, weight="bold", color="gray"),
            row_add_falta,
            ft.Container(height=5),
            col_lista_faltas
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True, scroll="auto")

        # ==========================================
        # ABA DE CONFIGURAÇÕES E PERFIL 
        # ==========================================
        def abrir_editar_perfil(e):
            email_atual = banco.obter_email_usuario()
            
            inp_email = ft.TextField(label="E-mail", value=email_atual)
            inp_nova = ft.TextField(label="Nova Senha (vazio para manter)", password=True, can_reveal_password=True)
            inp_conf = ft.TextField(label="Confirmar Nova Senha", password=True, can_reveal_password=True)
            
            def salvar_perfil(e_salv):
                novo_email = inp_email.value.strip()
                senha = inp_nova.value
                confirma = inp_conf.value
                
                if not novo_email:
                    show_snack("O E-mail não pode ficar vazio!", False)
                    return

                if senha or confirma:
                    if senha != confirma:
                        show_snack("As senhas não coincidem!", False)
                        return
                    if len(senha) < 4:
                        show_snack("A senha deve ter pelo menos 4 caracteres.", False)
                        return
                    
                    sucesso, msg = banco.atualizar_perfil(novo_email, senha)
                else:
                    sucesso, msg = banco.atualizar_perfil(novo_email)

                if sucesso:
                    dlg_perfil.open = False
                    show_snack("Perfil atualizado com sucesso!")
                else:
                    show_snack("Erro ao atualizar o perfil.", False)
            
            dlg_perfil = ft.AlertDialog(
                title=ft.Text("Editar Perfil"), 
                content=ft.Column([inp_email, inp_nova, inp_conf], tight=True), 
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg_perfil, 'open', False) or page.update()), 
                    ft.TextButton("Salvar", on_click=salvar_perfil)
                ]
            )
            page.overlay.append(dlg_perfil)
            dlg_perfil.open = True
            page.update()

        def alterar_tema(e):
            page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
            page.update()

        switch_tema = ft.Switch(label="Modo Escuro", value=True, on_change=alterar_tema)

        btn_editar_perfil = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.MANAGE_ACCOUNTS, color="white"), ft.Text("Editar Perfil", color="white", weight="bold")], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ft.Colors.BLUE_700, padding=10, border_radius=8, ink=True, on_click=abrir_editar_perfil, width=180
        )

        tela_config = ft.Column([
            ft.Text("Configurações", size=24, weight="bold"),
            ft.Container(height=10),
            ft.ListTile(leading=ft.Icon(ft.Icons.PERSON), title=ft.Text("Logado como"), subtitle=ft.Text(banco.USUARIO_NOME)),
            ft.Row([ft.Container(width=15), btn_editar_perfil]),
            ft.Container(height=10),
            switch_tema, 
            ft.Divider(height=20, color="transparent"),
            ft.Text("Sobre o Aplicativo", size=16, weight="bold", color="gray"),
            ft.ListTile(leading=ft.Icon(ft.Icons.BRUSH, color="purple"), title=ft.Text("Aplicativo"), subtitle=ft.Text("Meu Ateliê v1.1")),
            ft.ListTile(leading=ft.Icon(ft.Icons.CODE, color="blue"), title=ft.Text("Thiago Oliveira"), subtitle=ft.Text("Suporte: (00) 00000-0000")),
            ft.Container(height=30),
            ft.Container(content=ft.Text("SAIR DA CONTA", color="white", weight="bold"), bgcolor="red", padding=15, border_radius=8, alignment=ft.Alignment.CENTER, ink=True, on_click=sair_da_conta)
        ], scroll="auto", expand=True)

        # ==========================================
        # NAVEGAÇÃO PRINCIPAL 
        # ==========================================
        def mudar_aba(e):
            area_conteudo.content = [tela_inicio, tela_historico, tela_gestao, tela_config][e.control.selected_index]
            page.update()

        page.navigation_bar = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME, label="Início"),
                ft.NavigationBarDestination(icon=ft.Icons.RECEIPT_LONG, label="Histórico"),
                ft.NavigationBarDestination(icon=ft.Icons.CATEGORY, label="Gestão"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Ajustes")
            ], on_change=mudar_aba
        )
        
        page.add(area_conteudo)
        mudar_aba(type('obj', (object,), {'control': type('obj', (object,), {'selected_index': 0})}))
        atualizar_gestao()
        atualizar_dashboard_e_historico()

    # ==========================================
    # LOGIN COM RECUPERAÇÃO E REGISTRO
    # ==========================================
    txt_usuario = ft.TextField(label="Usuário", width=300, prefix_icon=ft.Icons.PERSON)
    txt_senha = ft.TextField(label="Senha", width=300, password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK)
    chk_lembrar = ft.Checkbox(label="Lembrar meu acesso", value=False)

    def tentar_login(e=None):
        u, p = txt_usuario.value, txt_senha.value
        sucesso, msg = banco.login_sistema(u, p)
        if sucesso:
            salvar_acesso(u, p) if chk_lembrar.value else limpar_acesso()
            page.clean()
            page.horizontal_alignment = ft.CrossAxisAlignment.START
            page.vertical_alignment = ft.MainAxisAlignment.START
            construir_app_principal() 
        else:
            show_snack(msg, False)

    def abrir_registro(e):
        inp_nome = ft.TextField(label="Nome Completo")
        inp_email = ft.TextField(label="E-mail")
        inp_usr = ft.TextField(label="Usuário (Login)")
        inp_pwd = ft.TextField(label="Senha", password=True, can_reveal_password=True)
        
        def salvar_registro(e_reg):
            if not all([inp_nome.value, inp_email.value, inp_usr.value, inp_pwd.value]): 
                show_snack("Preencha todos os campos!", False)
                return
            suc, msg = banco.registrar_novo_usuario(inp_nome.value, inp_email.value, inp_usr.value, inp_pwd.value)
            dlg_reg.open = False
            page.update()
            show_snack(msg, suc)

        dlg_reg = ft.AlertDialog(
            title=ft.Text("Criar Conta"), content=ft.Column([inp_nome, inp_email, inp_usr, inp_pwd], tight=True), 
            actions=[ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg_reg, 'open', False) or page.update()), ft.TextButton("Registar", on_click=salvar_registro)]
        )
        page.overlay.append(dlg_reg)
        dlg_reg.open = True
        page.update()

    def abrir_recuperacao(e):
        inp_email = ft.TextField(label="Digite o seu E-mail cadastrado")
        def enviar_recuperacao(e_rec):
            if not inp_email.value: return
            suc, msg = banco.redefinir_senha_por_email(inp_email.value)
            dlg_rec.open = False
            page.update()
            show_snack(msg, suc)

        dlg_rec = ft.AlertDialog(
            title=ft.Text("Recuperar Senha"), content=inp_email, 
            actions=[ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg_rec, 'open', False) or page.update()), ft.TextButton("Recuperar", on_click=enviar_recuperacao)]
        )
        page.overlay.append(dlg_rec)
        dlg_rec.open = True
        page.update()

    btn_entrar = ft.Container(content=ft.Text("ENTRAR", color="white", weight="bold", size=16), width=300, height=50, bgcolor=ft.Colors.PURPLE_700, border_radius=8, alignment=ft.Alignment.CENTER, ink=True, on_click=tentar_login)
    row_opcoes = ft.Row([ft.TextButton("Criar nova conta", on_click=abrir_registro), ft.TextButton("Esqueci a minha senha", on_click=abrir_recuperacao)], width=300, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    def renderizar_login():
        user_salvo, pass_salva = ler_acesso()
        if user_salvo and pass_salva:
            sucesso, msg = banco.login_sistema(user_salvo, pass_salva)
            if sucesso:
                txt_usuario.value, txt_senha.value, chk_lembrar.value = user_salvo, pass_salva, True
                page.clean()
                page.horizontal_alignment = ft.CrossAxisAlignment.START
                page.vertical_alignment = ft.MainAxisAlignment.START
                construir_app_principal()
                return

        page.clean()
        page.navigation_bar = None 
        page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        page.vertical_alignment = ft.MainAxisAlignment.CENTER
        
        txt_usuario.value = user_salvo if user_salvo else ""
        txt_senha.value = pass_salva if pass_salva else ""
        chk_lembrar.value = True if (user_salvo and pass_salva) else False

        page.add(
            ft.Icon(ft.Icons.BRUSH, size=80, color=ft.Colors.PURPLE_400),
            ft.Text("MEU ATELIÊ", size=28, weight="bold"),
            ft.Text("Gestão para Artesãs", size=14, color=ft.Colors.GREY_400),
            ft.Container(height=30), txt_usuario, txt_senha, ft.Container(content=chk_lembrar, width=300),
            ft.Container(height=10), btn_entrar, row_opcoes
        )
        page.update()

    renderizar_login()

ft.run(main)
