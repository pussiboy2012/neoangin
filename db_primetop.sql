

/*==============================================================*/
/* Table: Orders                                                */
/*==============================================================*/
create table Orders (
   id_order             SERIAL               not null,
   id_user              INT4                 not null,
   date_shipment        DATE                 null,
   cancelation_reason_order TEXT                 null,
   status_order         TEXT                 not null,
   created_at_order     DATE                 not null,
   updated_at_order     DATE                 null,
   constraint PK_ORDERS primary key (id_order)
);

/*==============================================================*/
/* Index: Orders_PK                                             */
/*==============================================================*/
create unique index Orders_PK on Orders (
id_order
);

/*==============================================================*/
/* Index: "user-order_FK"                                       */
/*==============================================================*/
create  index "user-order_FK" on Orders (
id_user
);

/*==============================================================*/
/* Table: Products                                              */
/*==============================================================*/
create table Products (
   id_product           SERIAL               not null,
   title_product        TEXT                 not null,
   price_product        DECIMAL              not null,
   created_at_product   DATE                 not null,
   category_product     TEXT                 not null,
   description_product  TEXT                 not null,
   img_path_product     TEXT                 not null,
   expiration_month_product INT4                 not null,
   nomenclature_product TEXT                 not null,
   constraint PK_PRODUCTS primary key (id_product)
);

/*==============================================================*/
/* Index: Products_PK                                           */
/*==============================================================*/
create unique index Products_PK on Products (
id_product
);

/*==============================================================*/
/* Table: Stocks                                                */
/*==============================================================*/
create table Stocks (
   id_stock             SERIAL               not null,
   id_product           INT4                 not null,
   id_analyzis          INT4                 null,
   count_stock          INT4                 not null,
   RAL_stock            VARCHAR(4)           null,
   date_stock           DATE                 not null,
   constraint PK_STOCKS primary key (id_stock)
);

/*==============================================================*/
/* Index: Stocks_PK                                             */
/*==============================================================*/
create unique index Stocks_PK on Stocks (
id_stock
);

/*==============================================================*/
/* Index: "product-stock_FK"                                    */
/*==============================================================*/
create  index "product-stock_FK" on Stocks (
id_product
);

/*==============================================================*/
/* Index: "stock-analyzis2_FK"                                  */
/*==============================================================*/
create  index "stock-analyzis2_FK" on Stocks (
id_analyzis
);

/*==============================================================*/
/* Table: Users                                                 */
/*==============================================================*/
create table Users (
   id_user              SERIAL               not null,
   username_user        TEXT                 not null,
   email_user           TEXT                 not null,
   fullname_user        TEXT                 not null,
   inn_user             VARCHAR(12)          not null,
   company_name_user    TEXT                 not null,
   phone_user           VARCHAR(16)          not null,
   password_hash_user   TEXT                 not null,
   role_user            VARCHAR(7)           not null,
   created_at_user      DATE                 not null,
   company_verified_user BOOL                 not null,

/*==============================================================*/
/* Index: Users_PK                                              */
/*==============================================================*/
create unique index Users_PK on Users (
id_user
);

/*==============================================================*/
/* Table: analyzis                                              */
/*==============================================================*/
create table analyzis (
   id_analyzis          SERIAL               not null,
   id_stock             INT4                 not null,
   glitter              FLOAT8               null,
   viskosity            FLOAT8               null,
   delta_E              FLOAT8               null,
   delta_L              FLOAT8               null,
   delta_a              FLOAT8               null,
   delta_b              FLOAT8               null,
   drying_time          FLOAT8               null,
   peak_metal_temperature FLOAT8               null,
   thickness_for_soil   FLOAT8               null,
   adhesion             FLOAT8               null,
   solvent_resistance   FLOAT8               null,
   visual_flat_control  TEXT                 null,
   appearance           TEXT                 null,
   number_of_batch_samples INT4                 null,
   degree_of_grinding   FLOAT8               null,
   solids_by_volume     FLOAT8               null,
   ground               FLOAT8               null,
   mass_fraction        FLOAT8               null,
   constraint PK_ANALYZIS primary key (id_analyzis)
);

/*==============================================================*/
/* Index: analyzis_PK                                           */
/*==============================================================*/
create unique index analyzis_PK on analyzis (
id_analyzis
);

/*==============================================================*/
/* Index: "stock-analyzis3_FK"                                  */
/*==============================================================*/
create  index "stock-analyzis3_FK" on analyzis (
id_stock
);

/*==============================================================*/
/* Table: "product-order"                                       */
/*==============================================================*/
create table "product-order" (
   id_product           INT4                 not null,
   id_order             INT4                 not null,
   count                INT4                 not null,
   RAL                  VARCHAR(4)           null,
   creating_date        DATE                 not null,
   constraint "PK_PRODUCT-ORDER" primary key (id_product, id_order)
);

/*==============================================================*/
/* Index: "product-order_PK"                                    */
/*==============================================================*/
create unique index "product-order_PK" on "product-order" (
id_product,
id_order
);

/*==============================================================*/
/* Index: "product-order3_FK"                                   */
/*==============================================================*/
create  index "product-order3_FK" on "product-order" (
id_product
);

/*==============================================================*/
/* Index: "product-order2_FK"                                   */
/*==============================================================*/
create  index "product-order2_FK" on "product-order" (
id_order
);

create table "stock-order" (
   id_stock             INT4                 not null,
   id_order             INT4                 not null,
   count_order          INT4                 null,
   constraint "PK_STOCK-ORDER" primary key (id_stock, id_order)
);


alter table "stock-order"
   add constraint "FK_STOCK-OR_STOCK-ORD_STOCKS" foreign key (id_stock)
      references Stocks (id_stock)
      on delete restrict on update restrict;

alter table "stock-order"
   add constraint "FK_STOCK-OR_STOCK-ORD_ORDERS" foreign key (id_order)
      references Orders (id_order)
      on delete restrict on update restrict;

alter table Orders
   add constraint "FK_ORDERS_USER-ORDE_USERS" foreign key (id_user)
      references Users (id_user)
      on delete restrict on update restrict;

alter table Stocks
   add constraint "FK_STOCKS_PRODUCT-S_PRODUCTS" foreign key (id_product)
      references Products (id_product)
      on delete restrict on update restrict;

alter table Stocks
   add constraint "FK_STOCKS_STOCK-ANA_ANALYZIS" foreign key (id_analyzis)
      references analyzis (id_analyzis)
      on delete restrict on update restrict;

alter table analyzis
   add constraint "FK_ANALYZIS_STOCK-ANA_STOCKS" foreign key (id_stock)
      references Stocks (id_stock)
      on delete restrict on update restrict;

alter table "product-order"
   add constraint "FK_PRODUCT-_PRODUCT-O_ORDERS" foreign key (id_order)
      references Orders (id_order)
      on delete restrict on update restrict;

alter table "product-order"
   add constraint "FK_PRODUCT-_PRODUCT-O_PRODUCTS" foreign key (id_product)
      references Products (id_product)
      on delete restrict on update restrict;




/*==============================================================*/
/* View: product_stock_series                                   */
/*==============================================================*/
CREATE VIEW public.product_stock_series AS
 SELECT concat(p.nomenclature_product,
        CASE
            WHEN (s.ral_stock IS NOT NULL) THEN concat(' RAL ', s.ral_stock)
            ELSE ''::text
        END) AS nomenclature_ral,
    concat('п.', s.id_stock, ' от ', to_char((s.date_stock)::timestamp with time zone, 'DD.MM.YYYY'::text), ' до ', to_char((s.date_stock + ((p.expiration_month_product || ' months'::text))::interval), 'DD.MM.YYYY'::text)) AS series_info,
    s.count_stock AS remaining_quantity
   FROM (public.stocks s
     JOIN public.products p ON ((s.id_product = p.id_product)))
  WHERE (s.count_stock > 0);
